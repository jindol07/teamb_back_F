package kr.co.alpharking.service.mypage;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import java.util.Optional;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;
import org.mockito.ArgumentCaptor;
import kr.co.alpharking.dto.mypage.MyPageDtos.PasswordChangeRequest;
import kr.co.alpharking.dto.mypage.MyPageDtos.WithdrawRequest;
import kr.co.alpharking.repository.mypage.MyPageOfficeRepository;
import kr.co.alpharking.repository.mypage.MyPageCompanyRepository;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.security.Company;

class MyPageAccountServiceTest {
    private final MyPageOfficeRepository offices = mock(MyPageOfficeRepository.class);
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder(4);
    private final MyPageCompanyRepository companies = mock(MyPageCompanyRepository.class);
    private final MyPageAccountService service = new MyPageAccountService(offices, encoder, companies);
    private Office office;
    private String originalHash;

    @BeforeEach
    // 활성 계정과 BCrypt 비밀번호 해시를 테스트용으로 준비한다.
    void setUp() {
        office = new Office(); office.setOffice_id(12L); office.setStatus_code("ACTIVE");
        originalHash = encoder.encode("old-password");
        office.setPassword(originalHash);
        when(offices.lockOffice(12L)).thenReturn(Optional.of(office));
    }

    @Test
    // 가입과 같은 인코더로 새 비밀번호를 해시해 갱신하는지 검증한다.
    void updatesOnlyHashedPasswordUsingTheSignupEncoder() {
        service.changePassword(12L, new PasswordChangeRequest("old-password", "new-password", "new-password"));
        assertTrue(encoder.matches("new-password", office.getPassword()));
        assertNotEquals("new-password", office.getPassword());
        assertFalse(encoder.matches("old-password", office.getPassword()));
        verify(offices).updateTimestamp(12L);
        verify(offices).flush();
    }

    @Test
    // 현재 비밀번호가 틀리면 계정 정보를 변경하지 않는지 검증한다.
    void wrongCurrentPasswordNeverUpdatesAnything() {
        var error = assertThrows(ResponseStatusException.class, () -> service.changePassword(12L,
                new PasswordChangeRequest("wrong-password", "new-password", "new-password")));
        assertEquals(HttpStatus.BAD_REQUEST, error.getStatusCode());
        assertEquals(originalHash, office.getPassword());
        verify(offices, never()).updateTimestamp(anyLong());
        verify(offices, never()).flush();
    }

    @Test
    // 새 비밀번호 길이·확인 불일치를 DB 조회 전에 거절하는지 검증한다.
    void invalidNewPasswordAndMismatchAreRejectedBeforeDatabaseLookup() {
        assertThrows(ResponseStatusException.class, () -> service.changePassword(12L,
                new PasswordChangeRequest("old-password", "short", "short")));
        assertThrows(ResponseStatusException.class, () -> service.changePassword(12L,
                new PasswordChangeRequest("old-password", "new-password", "different-password")));
        verify(offices, never()).lockOffice(anyLong());
    }

    @Test
    // 탈퇴 등 비활성 계정은 비밀번호를 변경할 수 없는지 검증한다.
    void inactiveOfficeCannotChangePassword() {
        office.setStatus_code("WITHDRAWN");
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class, () -> service.changePassword(12L,
                new PasswordChangeRequest("old-password", "new-password", "new-password"))).getStatusCode());
        assertEquals(originalHash, office.getPassword());
    }

    // 유니크 충돌이나 다른 회사 회원이 없는 정상 탈퇴 조건을 mock으로 준비한다.
    private void canWithdraw() {
        office.setCompany_id(9L); office.setUsername("member"); office.setEmail("member@example.test");
        office.setPhone(null);
        var company = new Company(); company.setCompany_id(9L); company.setBusiness_number("1234567890");
        when(companies.lockCompany(9L)).thenReturn(Optional.of(company));
        when(offices.deletionDay()).thenReturn("1027");
        when(offices.withdraw(eq(12L), eq("member_d_1027"), eq("member@example.test_d_1027"), isNull(), anyString())).thenReturn(1);
        when(companies.softDelete(9L, "1234567890_d_1027")).thenReturn(1);
    }

    @Test
    // 회사·사무실의 소프트 삭제 순서와 유니크 값·비밀번호 해시 변경을 검증한다.
    void withdrawalRenamesOnlySpecifiedUniqueValuesAndSoftDeletesBothRows() {
        // 유니크 충돌이나 다른 회사 회원이 없는 정상 탈퇴 조건을 mock으로 준비한다.
        canWithdraw();
        service.withdraw(12L, new WithdrawRequest("old-password", "탈퇴"));
        var order = inOrder(offices, companies);
        order.verify(offices).lockOffice(12L);
        order.verify(companies).lockCompany(9L);
        order.verify(offices).countOtherMembers(9L, 12L);
        order.verify(offices).deletionDay();
        order.verify(offices).countUniqueConflicts(12L, "member_d_1027", "member@example.test_d_1027", null);
        order.verify(companies).countBusinessConflicts(9L, "1234567890_d_1027");
        var hash = ArgumentCaptor.forClass(String.class);
        order.verify(offices).withdraw(eq(12L), eq("member_d_1027"), eq("member@example.test_d_1027"), isNull(), hash.capture());
        assertTrue(hash.getValue().startsWith("$2"));
        assertFalse(encoder.matches("old-password", hash.getValue()));
        order.verify(companies).softDelete(9L, "1234567890_d_1027");
        verify(offices, never()).delete(any(Office.class));
        verify(companies, never()).delete(any(Company.class));
    }

    @Test
    // 같은 회사에 다른 회원이 있으면 탈퇴 갱신이 실행되지 않는지 검증한다.
    void otherCompanyMemberPreventsDeletingCompanyOrOffice() {
        // 유니크 충돌이나 다른 회사 회원이 없는 정상 탈퇴 조건을 mock으로 준비한다.
        canWithdraw();
        when(offices.countOtherMembers(9L, 12L)).thenReturn(1L);
        assertEquals(HttpStatus.CONFLICT, assertThrows(ResponseStatusException.class,
                () -> service.withdraw(12L, new WithdrawRequest("old-password", "탈퇴"))).getStatusCode());
        verify(offices, never()).withdraw(anyLong(), anyString(), anyString(), nullable(String.class), anyString());
        verify(companies, never()).softDelete(anyLong(), anyString());
    }

    @Test
    // 탈퇴 접미사 값이 기존 값과 충돌하면 DB 변경을 하지 않는지 검증한다.
    void sameDayUniqueCollisionNeverWrites() {
        // 유니크 충돌이나 다른 회사 회원이 없는 정상 탈퇴 조건을 mock으로 준비한다.
        canWithdraw();
        when(offices.countUniqueConflicts(anyLong(), anyString(), anyString(), nullable(String.class))).thenReturn(1L);
        assertThrows(ResponseStatusException.class, () -> service.withdraw(12L, new WithdrawRequest("old-password", "탈퇴")));
        verify(offices, never()).withdraw(anyLong(), anyString(), anyString(), nullable(String.class), anyString());
        verify(companies, never()).softDelete(anyLong(), anyString());
    }

    @Test
    // 비밀번호나 탈퇴 확인 문구가 틀리면 탈퇴하지 않는지 검증한다.
    void wrongPasswordOrMissingConfirmationNeverDeletes() {
        assertThrows(ResponseStatusException.class, () -> service.withdraw(12L, new WithdrawRequest("old-password", "")));
        verify(offices, never()).lockOffice(anyLong());
        assertThrows(ResponseStatusException.class, () -> service.withdraw(12L, new WithdrawRequest("wrong-password", "탈퇴")));
        verifyNoInteractions(companies);
    }

    @Test
    // 탈퇴 접미사가 null과 유니코드를 안전하게 처리하고 BYTE 제한을 지키는지 검증한다.
    void deletedValuePreservesNullAndFitsOracleByteLimitsWithoutSplittingUnicode() {
        assertNull(MyPageAccountService.deletedValue(null, 50, "1027"));
        assertEquals("member_d_1027", MyPageAccountService.deletedValue("member", 50, "1027"));
        assertEquals(50, MyPageAccountService.deletedValue("a".repeat(50), 50, "1027").length());
        String unicode = MyPageAccountService.deletedValue("한😀".repeat(30), 50, "1027");
        assertTrue(unicode.getBytes(StandardCharsets.UTF_8).length <= 50);
        assertTrue(unicode.endsWith("_d_1027"));
        assertFalse(unicode.contains("\uFFFD"));
    }

    static class TrackingTransactions extends AbstractPlatformTransactionManager {
        boolean committed;
        boolean rolledBack;
        // 테스트에서 사용할 트랜잭션 식별 객체를 생성한다.
        @Override protected Object doGetTransaction() { return new Object(); }
        // 쓰기 트랜잭션으로 실행되는지 확인한다.
        @Override protected void doBegin(Object tx, TransactionDefinition definition) { assertFalse(definition.isReadOnly()); }
        // 테스트 대상 트랜잭션이 커밋되었음을 기록한다.
        @Override protected void doCommit(DefaultTransactionStatus status) { committed = true; }
        // 테스트 대상 트랜잭션이 롤백되었음을 기록한다.
        @Override protected void doRollback(DefaultTransactionStatus status) { rolledBack = true; }
    }

    @Test
    // 회사 갱신 실패 시 먼저 실행한 사무실 탈퇴도 롤백을 요청하는지 검증한다.
    void companyFailureRollsBackOfficeWithdrawalToo() {
        // 유니크 충돌이나 다른 회사 회원이 없는 정상 탈퇴 조건을 mock으로 준비한다.
        canWithdraw();
        when(companies.softDelete(9L, "1234567890_d_1027")).thenReturn(0);
        var manager = new TrackingTransactions();
        var interceptor = new TransactionInterceptor();
        interceptor.setTransactionManager(manager);
        interceptor.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
        var factory = new ProxyFactory(service); factory.addAdvice(interceptor);
        var transactional = (MyPageAccountService) factory.getProxy();
        assertThrows(ResponseStatusException.class, () -> transactional.withdraw(12L, new WithdrawRequest("old-password", "탈퇴")));
        assertTrue(manager.rolledBack);
        assertFalse(manager.committed);
    }
}
