package kr.co.alpharking.service.mypage;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import java.math.BigDecimal;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.mypage.MyPageDtos.PenaltyRow;
import kr.co.alpharking.entity.mypage.*;
import kr.co.alpharking.repository.mypage.*;
import kr.co.alpharking.security.Office;

class MyPagePenaltyServiceTest {
    private final MyPageOfficeRepository offices = mock(MyPageOfficeRepository.class);
    private final OfficeChargeRepository charges = mock(OfficeChargeRepository.class);
    private final OfficeChargeItemRepository items = mock(OfficeChargeItemRepository.class);
    private final MyPagePenaltyRepository penalties = mock(MyPagePenaltyRepository.class);
    private final MyPagePenaltyService service = new MyPagePenaltyService(offices, charges, items, penalties);
    private OfficeCharge charge;
    private VehiclePenalty penalty;
    private Office office;
    private String month;

    // 본인 사무실·당월 청구·아직 청구되지 않은 패널티를 테스트용으로 준비한다.
    @BeforeEach
    void setUp() {
        month = YearMonth.now(ZoneId.of("Asia/Seoul")).format(DateTimeFormatter.ofPattern("yyyyMM"));
        office = new Office(); office.setOffice_id(15L); office.setStatus_code("ACTIVE");
        charge = OfficeCharge.forPenalty(15L, month, LocalDateTime.now());
        ReflectionTestUtils.setField(charge, "id", 80L);
        ReflectionTestUtils.setField(charge, "totalAmount", new BigDecimal("85000"));
        ReflectionTestUtils.setField(charge, "finalAmount", new BigDecimal("85000"));
        penalty = new VehiclePenalty();
        ReflectionTestUtils.setField(penalty, "id", 55L);
        ReflectionTestUtils.setField(penalty, "amount", new BigDecimal("10000"));
        when(offices.lockOffice(15L)).thenReturn(Optional.of(office));
        when(charges.lockCurrent(15L, month)).thenReturn(List.of(charge));
        when(penalties.lockUnbilled(eq(15L), any(), any())).thenReturn(List.of(penalty));
    }

    // 패널티 10,000원이 기존 관리비 85,000원에 한 번 합산되고 참조 ID가 저장되는지 검증한다.
    @Test
    void addsPenaltyToExistingBillAndReferencesActualPenaltyId() {
        service.synchronize(15L);
        assertEquals(0, new BigDecimal("95000").compareTo(charge.getTotalAmount()));
        assertEquals(0, new BigDecimal("95000").compareTo(charge.getFinalAmount()));
        var captor = ArgumentCaptor.forClass(List.class);
        verify(items).saveAllAndFlush(captor.capture());
        var item = (OfficeChargeItem) captor.getValue().get(0);
        assertEquals("PENALTY", item.getChargeTypeCode());
        assertEquals(55L, item.getReferenceId());
        assertEquals(80L, item.getChargeId());
        assertEquals(0, penalty.getAmount().compareTo(item.getAmount()));
        verify(charges, never()).saveAndFlush(any());
        var order = inOrder(offices, charges, penalties, items);
        order.verify(offices).lockOffice(15L);
        order.verify(charges).lockCurrent(15L, month);
        order.verify(penalties).lockUnbilled(eq(15L), any(), any());
        order.verify(items).saveAllAndFlush(anyList());
    }

    // 청구가 없으면 새 청구를 생성하고 패널티만큼의 금액을 기록하는지 검증한다.
    @Test
    void createsMonthlyBillWhenOnlyUnbilledPenaltyExists() {
        when(charges.lockCurrent(15L, month)).thenReturn(List.of());
        when(charges.saveAndFlush(any())).thenAnswer(invocation -> {
            OfficeCharge created = invocation.getArgument(0);
            ReflectionTestUtils.setField(created, "id", 99L);
            return created;
        });
        service.synchronize(15L);
        var captor = ArgumentCaptor.forClass(OfficeCharge.class);
        verify(charges).saveAndFlush(captor.capture());
        var created = captor.getValue();
        assertEquals(15L, created.getOfficeId());
        assertEquals(month, created.getYearMonth());
        assertEquals("BILLED", created.getStatusCode());
        assertEquals(0, new BigDecimal("10000").compareTo(created.getFinalAmount()));
        assertEquals(0, created.getMileageDiscountAmount().signum());
    }

    // 미반영 패널티가 없으면 불필요한 청구나 상세를 만들지 않는지 검증한다.
    @Test
    void noPendingPenaltyDoesNotCreateEmptyBill() {
        when(charges.lockCurrent(15L, month)).thenReturn(List.of());
        when(penalties.lockUnbilled(eq(15L), any(), any())).thenReturn(List.of());
        service.synchronize(15L);
        verify(charges, never()).saveAndFlush(any());
        verifyNoInteractions(items);
    }

    // 이미 청구된 패널티가 다음 미반영 조회에서 제외되면 금액이 다시 더해지지 않는지 검증한다.
    @Test
    void repeatedSynchronizationDoesNotBillSamePenaltyAgain() {
        when(penalties.lockUnbilled(eq(15L), any(), any())).thenReturn(List.of(penalty), List.of());
        service.synchronize(15L); service.synchronize(15L);
        assertEquals(0, new BigDecimal("95000").compareTo(charge.getTotalAmount()));
        verify(items, times(1)).saveAllAndFlush(anyList());
    }

    // 잠금 대기 사이 이미 반영된 패널티는 최신 상세 존재 검사에서 다시 제외하는지 검증한다.
    @Test
    void alreadyBilledPenaltyFromStaleSelectionIsSkippedAfterLock() {
        when(items.existsByChargeTypeCodeAndReferenceId("PENALTY", 55L)).thenReturn(true);
        service.synchronize(15L);
        assertEquals(0, new BigDecimal("85000").compareTo(charge.getTotalAmount()));
        verify(items, never()).saveAllAndFlush(anyList());
        verify(charges, never()).saveAndFlush(any());
    }

    // 기존 마일리지 할인액을 유지한 채 패널티를 최종 관리비에 더하는지 검증한다.
    @Test
    void preservesPreviouslyUsedMileageDiscount() {
        ReflectionTestUtils.setField(charge, "mileageDiscountAmount", new BigDecimal("20000"));
        ReflectionTestUtils.setField(charge, "finalAmount", new BigDecimal("65000"));
        service.synchronize(15L);
        assertEquals(0, new BigDecimal("20000").compareTo(charge.getMileageDiscountAmount()));
        assertEquals(0, new BigDecimal("75000").compareTo(charge.getFinalAmount()));
    }

    // 납부 완료 청구를 다시 열지 않고 신규 패널티용 추가 청구를 생성하는지 검증한다.
    @Test
    void paidBillRemainsUntouchedAndNewPenaltyGetsSupplementaryBill() {
        ReflectionTestUtils.setField(charge, "statusCode", "PAID");
        when(charges.saveAndFlush(any())).thenAnswer(invocation -> {
            OfficeCharge created = invocation.getArgument(0);
            ReflectionTestUtils.setField(created, "id", 99L); return created;
        });
        service.synchronize(15L);
        assertEquals("PAID", charge.getStatusCode());
        assertEquals(0, new BigDecimal("85000").compareTo(charge.getTotalAmount()));
        verify(charges).saveAndFlush(any());
    }

    // 청구 준비 중인 금액에는 패널티를 반영하되 청구 상태를 임의로 확정하지 않는지 검증한다.
    @Test
    void readyBillKeepsItsStatus() {
        ReflectionTestUtils.setField(charge, "statusCode", "READY");
        service.synchronize(15L);
        assertEquals("READY", charge.getStatusCode());
    }

    // 비활성 계정의 청구 갱신과 금액이 불일치하는 청구의 합산을 거절하는지 검증한다.
    @Test
    void inactiveOfficeAndInconsistentBillNeverInsertItems() {
        office.setStatus_code("WITHDRAWN");
        assertThrows(ResponseStatusException.class, () -> service.synchronize(15L));
        office.setStatus_code("ACTIVE");
        ReflectionTestUtils.setField(charge, "finalAmount", BigDecimal.ONE);
        assertThrows(ResponseStatusException.class, () -> service.synchronize(15L));
        verify(items, never()).saveAllAndFlush(anyList());
    }

    // NUMBER(12,2) 범위를 넘는 청구 증가를 저장 전에 거절하는지 검증한다.
    @Test
    void rejectsInvoiceAmountOverflow() {
        ReflectionTestUtils.setField(charge, "totalAmount", new BigDecimal("9999999999.99"));
        ReflectionTestUtils.setField(charge, "finalAmount", new BigDecimal("9999999999.99"));
        assertThrows(ResponseStatusException.class, () -> service.synchronize(15L));
        verify(items, never()).saveAllAndFlush(anyList());
    }

    // 부과 월 범위가 한국 시간의 당월 시작 이상·다음 달 시작 미만으로 전달되는지 검증한다.
    @Test
    void pendingQueryUsesCurrentMonthBoundaries() {
        service.synchronize(15L);
        YearMonth current = YearMonth.now(ZoneId.of("Asia/Seoul"));
        verify(penalties).lockUnbilled(15L, current.atDay(1).atStartOfDay(), current.plusMonths(1).atDay(1).atStartOfDay());
    }

    // 패널티 응답에 실제 금액과 공통코드 표시명을 담고 페이지 범위를 제한하는지 검증한다.
    @Test
    void penaltyResponseIncludesAmountAndCodeName() {
        var row = mock(PenaltyRow.class);
        when(row.getPenaltyAmount()).thenReturn(new BigDecimal("10000"));
        when(row.getTypeName()).thenReturn("지정구역위반");
        when(penalties.findOwned(15L, PageRequest.of(0, 10))).thenReturn(new PageImpl<>(List.of(row)));
        var result = service.findOwned(15L, 0, 10).getContent().get(0);
        assertEquals(0, new BigDecimal("10000").compareTo(result.penaltyAmount()));
        assertEquals("지정구역위반", result.typeName());
        assertThrows(ResponseStatusException.class, () -> service.findOwned(15L, -1, 10));
        assertThrows(ResponseStatusException.class, () -> service.findOwned(15L, 0, 51));
    }

    static class TrackingTransactions extends AbstractPlatformTransactionManager {
        boolean committed;
        boolean rolledBack;
        // 테스트용 트랜잭션 객체를 생성한다.
        @Override protected Object doGetTransaction() { return new Object(); }
        // 패널티 합산이 쓰기 트랜잭션으로 실행되는지 확인한다.
        @Override protected void doBegin(Object tx, TransactionDefinition definition) { assertFalse(definition.isReadOnly()); }
        // 커밋 여부를 기록한다.
        @Override protected void doCommit(DefaultTransactionStatus status) { committed = true; }
        // 롤백 여부를 기록한다.
        @Override protected void doRollback(DefaultTransactionStatus status) { rolledBack = true; }
    }

    // 상세 저장에 실패하면 청구 생성·금액 갱신도 같은 트랜잭션에서 롤백되는지 검증한다.
    @Test
    void itemPersistenceFailureRollsBackWholeSynchronization() {
        when(items.saveAllAndFlush(anyList())).thenThrow(new IllegalStateException("simulated insert failure"));
        var manager = new TrackingTransactions();
        var interceptor = new TransactionInterceptor();
        interceptor.setTransactionManager(manager);
        interceptor.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
        var proxy = new ProxyFactory(service); proxy.addAdvice(interceptor);
        var transactional = (MyPagePenaltyService) proxy.getProxy();
        assertThrows(IllegalStateException.class, () -> transactional.synchronize(15L));
        assertTrue(manager.rolledBack); assertFalse(manager.committed);
    }
}
