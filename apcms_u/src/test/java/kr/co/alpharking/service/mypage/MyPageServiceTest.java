package kr.co.alpharking.service.mypage;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import java.math.BigDecimal;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.mileage.MileagehistoryDto;
import kr.co.alpharking.dto.mypage.MyPageDtos.*;
import kr.co.alpharking.entity.mypage.OfficeCharge;
import kr.co.alpharking.repository.mypage.*;
import kr.co.alpharking.security.Office;

class MyPageServiceTest {
    private final MyPageOfficeRepository offices = mock(MyPageOfficeRepository.class);
    private final OfficeChargeRepository charges = mock(OfficeChargeRepository.class);
    private final OfficeChargeItemRepository items = mock(OfficeChargeItemRepository.class);
    private final MyPageMileageRepository mileage = mock(MyPageMileageRepository.class);
    private final MyPageParkingUsageRepository usages = mock(MyPageParkingUsageRepository.class);
    private final MyPageReportRepository reports = mock(MyPageReportRepository.class);
    private final MyPagePenaltyService penalties = mock(MyPagePenaltyService.class);
    private final MyPageService service = new MyPageService(offices, charges, items, mileage, usages, reports, penalties);
    private OfficeCharge charge;
    private Office office;

    @BeforeEach
    // 테스트용 활성 사무실과 당월 관리비 엔티티를 구성한다.
    void setUp() {
        office = new Office();
        office.setOffice_id(12L);
        office.setStatus_code("ACTIVE");
        charge = new OfficeCharge();
        ReflectionTestUtils.setField(charge, "id", 33L);
        ReflectionTestUtils.setField(charge, "officeId", 12L);
        ReflectionTestUtils.setField(charge, "yearMonth", YearMonth.now(ZoneId.of("Asia/Seoul"))
                .format(DateTimeFormatter.ofPattern("yyyyMM")));
        ReflectionTestUtils.setField(charge, "statusCode", "BILLED");
        ReflectionTestUtils.setField(charge, "totalAmount", new BigDecimal("85000.00"));
        ReflectionTestUtils.setField(charge, "mileageDiscountAmount", BigDecimal.ZERO);
        ReflectionTestUtils.setField(charge, "finalAmount", new BigDecimal("85000.00"));
    }

    // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
    private void usable() {
        when(offices.lockOffice(12L)).thenReturn(Optional.of(office));
        when(charges.lockOwned(33L, 12L)).thenReturn(Optional.of(charge));
        when(mileage.balance(12L)).thenReturn(new BigDecimal("120000"));
        when(charges.findCurrent(eq(12L), anyString())).thenReturn(List.of());
    }

    // 테스트에 사용할 초기 누적 할인액 기준의 마일리지 사용 요청을 만든다.
    private MileageUseRequest request(long amount) { return new MileageUseRequest(amount, BigDecimal.ZERO); }

    @Test
    // 부분 사용 시 잠금 순서와 청구에 연결된 음수 마일리지 이력 저장을 검증한다.
    void partialUseLocksOfficeBeforeChargeAndWritesNegativeLinkedHistory() {
        // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
        usable();
        service.useMileage(12L, 33L, request(10000));
        assertEquals(0, new BigDecimal("10000").compareTo(charge.getMileageDiscountAmount()));
        assertEquals(0, new BigDecimal("75000").compareTo(charge.getFinalAmount()));
        assertEquals("BILLED", charge.getStatusCode());
        var order = inOrder(offices, charges, mileage);
        order.verify(offices).lockOffice(12L);
        order.verify(charges).lockOwned(33L, 12L);
        order.verify(mileage).balance(12L);
        var captor = ArgumentCaptor.forClass(MileagehistoryDto.class);
        order.verify(mileage).saveAndFlush(captor.capture());
        assertEquals(-10000L, captor.getValue().getAmount());
        assertEquals("USE", captor.getValue().getMileagetypecode());
        assertEquals("OFFICE_CHARGE", captor.getValue().getReferencetypecode());
        assertEquals(33L, captor.getValue().getReferenceid());
        assertSame(office, captor.getValue().getOffice());
    }

    @Test
    // 전액 사용 시 납부 완료로 변경되고 청구 상세가 추가되지 않는지 검증한다.
    void fullUseMarksPaidAndDoesNotCreateChargeItems() {
        // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
        usable();
        service.useMileage(12L, 33L, request(85000));
        assertEquals(0, charge.getFinalAmount().signum());
        assertEquals("PAID", charge.getStatusCode());
        verifyNoInteractions(items);
    }

    @Test
    // 같은 누적 할인액을 사용한 재요청이 중복 차감되지 않는지 검증한다.
    void duplicateRequestIsRejectedBeforeAnotherHistoryWrite() {
        // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
        usable();
        service.useMileage(12L, 33L, request(10000));
        assertEquals(HttpStatus.CONFLICT, assertThrows(ResponseStatusException.class,
                () -> service.useMileage(12L, 33L, request(10000))).getStatusCode());
        verify(mileage, times(1)).saveAndFlush(any());
    }

    @Test
    // 최신 누적 할인액을 전달한 추가 사용 요청은 처리되는지 검증한다.
    void laterIntentionalUseAcceptsUpdatedCumulativeDiscount() {
        // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
        usable();
        service.useMileage(12L, 33L, request(10000));
        service.useMileage(12L, 33L, new MileageUseRequest(5000L, new BigDecimal("10000.00")));
        assertEquals(0, new BigDecimal("15000").compareTo(charge.getMileageDiscountAmount()));
        verify(mileage, times(2)).saveAndFlush(any());
    }

    @Test
    // 1,000P 단위를 벗어난 요청이 DB 잠금 전에 거절되는지 검증한다.
    void invalidUnitsNeverAcquireLocks() {
        for (long amount : new long[] { -1000, 0, 999, 1001 }) {
            assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class,
                    () -> service.useMileage(12L, 33L, request(amount))).getStatusCode());
        }
        verifyNoInteractions(offices, charges, mileage);
    }

    @Test
    // 본인 소유가 아닌 청구에 마일리지를 사용할 수 없는지 검증한다.
    void foreignChargeIsNotFoundAndCannotUseMileage() {
        when(offices.lockOffice(12L)).thenReturn(Optional.of(office));
        when(charges.lockOwned(33L, 12L)).thenReturn(Optional.empty());
        assertEquals(HttpStatus.NOT_FOUND, assertThrows(ResponseStatusException.class,
                () -> service.useMileage(12L, 33L, request(1000))).getStatusCode());
        verifyNoInteractions(mileage);
    }

    @Test
    // 잔액 부족 또는 청구액 초과 요청이 이력을 저장하지 않는지 검증한다.
    void insufficientBalanceAndExcessChargeNeverWriteHistory() {
        // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
        usable();
        when(mileage.balance(12L)).thenReturn(new BigDecimal("999"));
        assertThrows(ResponseStatusException.class, () -> service.useMileage(12L, 33L, request(1000)));
        assertThrows(ResponseStatusException.class, () -> service.useMileage(12L, 33L, request(86000)));
        verify(mileage, never()).saveAndFlush(any());
    }

    @Test
    // 청구 완료 상태가 아니거나 당월이 아닌 관리비의 사용을 거절하는지 검증한다.
    void nonBilledAndPastMonthChargesAreRejected() {
        // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
        usable();
        for (String status : List.of("READY", "PAID")) {
            ReflectionTestUtils.setField(charge, "statusCode", status);
            assertThrows(ResponseStatusException.class, () -> service.useMileage(12L, 33L, request(1000)));
        }
        ReflectionTestUtils.setField(charge, "statusCode", "BILLED");
        ReflectionTestUtils.setField(charge, "yearMonth", "200001");
        assertThrows(ResponseStatusException.class, () -> service.useMileage(12L, 33L, request(1000)));
        verify(mileage, never()).saveAndFlush(any());
    }

    @Test
    // 금액 정합성이 깨진 청구와 비활성 계정의 사용을 거절하는지 검증한다.
    void inconsistentChargeAndInactiveAccountAreRejected() {
        // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
        usable();
        ReflectionTestUtils.setField(charge, "finalAmount", BigDecimal.ONE);
        assertThrows(ResponseStatusException.class, () -> service.useMileage(12L, 33L, request(1000)));
        office.setStatus_code("WITHDRAWN");
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                () -> service.useMileage(12L, 33L, request(1000))).getStatusCode());
        verify(mileage, never()).saveAndFlush(any());
    }

    @Test
    // 당월 청구가 없으면 빈 목록을 반환하고 상세 조회를 생략하는지 검증한다.
    void noMonthlyChargeReturnsEmptyAndDoesNotQueryItems() {
        when(charges.findCurrent(eq(12L), anyString())).thenReturn(List.of());
        when(mileage.balance(12L)).thenReturn(BigDecimal.ZERO);
        assertTrue(service.currentCharges(12L).charges().isEmpty());
        verifyNoInteractions(items);
    }

    @Test
    // 페이지 범위 검사와 공통코드 표시명의 응답 반영을 검증한다.
    void pageSizeIsBoundedAndCodeNamesComeFromQueryProjection() {
        var row = mock(ParkingUsageRow.class);
        when(row.getParkingTypeName()).thenReturn("공통코드 표시명");
        when(usages.findOwned(12L, PageRequest.of(2, 10))).thenReturn(new PageImpl<>(List.of(row)));
        assertEquals("공통코드 표시명", service.parkingUsages(12L, 2, 10).getContent().get(0).parkingTypeName());
        assertThrows(ResponseStatusException.class, () -> service.parkingUsages(12L, -1, 10));
        assertThrows(ResponseStatusException.class, () -> service.acceptedReports(12L, 0, 51));
    }

    static class TrackingTransactions extends AbstractPlatformTransactionManager {
        boolean committed;
        boolean rolledBack;
        // 테스트에서 사용할 트랜잭션 식별 객체를 생성한다.
        @Override protected Object doGetTransaction() { return new Object(); }
        // 쓰기 트랜잭션으로 실행되는지 확인한다.
        @Override protected void doBegin(Object tx, TransactionDefinition definition) {
            assertFalse(definition.isReadOnly());
        }
        // 테스트 대상 트랜잭션이 커밋되었음을 기록한다.
        @Override protected void doCommit(DefaultTransactionStatus status) { committed = true; }
        // 테스트 대상 트랜잭션이 롤백되었음을 기록한다.
        @Override protected void doRollback(DefaultTransactionStatus status) { rolledBack = true; }
    }

    @Test
    // 이력 저장 실패 시 서비스 트랜잭션 전체가 롤백을 요청하는지 검증한다.
    void persistenceFailureRequestsRollbackOfEntireServiceTransaction() {
        // 차감 가능한 사무실·청구·잔액 조회 결과를 mock으로 준비한다.
        usable();
        when(mileage.saveAndFlush(any())).thenThrow(new IllegalStateException("simulated write failure"));
        var manager = new TrackingTransactions();
        var interceptor = new TransactionInterceptor();
        interceptor.setTransactionManager(manager);
        interceptor.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
        var proxy = new ProxyFactory(service);
        proxy.addAdvice(interceptor);
        var transactional = (MyPageService) proxy.getProxy();
        assertThrows(IllegalStateException.class, () -> transactional.useMileage(12L, 33L, request(1000)));
        assertTrue(manager.rolledBack);
        assertFalse(manager.committed);
    }

    // 마일리지 사용 직전 새 패널티를 반영한 최종 금액으로 사용 한도를 검사하는지 검증한다.
    @Test
    void paymentRechecksPenaltyBeforeReadingChargeAndValidatingAmount() {
        usable();
        doAnswer(invocation -> {
            charge.addPenalty(new BigDecimal("10000")); return null;
        }).when(penalties).synchronize(12L);
        service.useMileage(12L, 33L, request(90000));
        assertEquals(0, new BigDecimal("5000").compareTo(charge.getFinalAmount()));
        var order = inOrder(offices, penalties, charges, mileage);
        order.verify(offices).lockOffice(12L);
        order.verify(penalties).synchronize(12L);
        order.verify(charges).lockOwned(33L, 12L);
        order.verify(mileage).balance(12L);
        order.verify(mileage).saveAndFlush(any());
    }
}
