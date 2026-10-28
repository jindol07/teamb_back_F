package kr.co.alpharking.controller.mileage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.security.Admin;

// by팀장: 관리자 차감의 잔액 검증과 OFFICE 잠금 순서를 검증한다. 실제 DB 동시성은 통합 검증이 필요하다.
class AdminMileageControllerTest {
    private JdbcTemplate jdbc;
    private AdminMileageController controller;
    private Admin admin;

    @BeforeEach
    // 관리자 계정과 JDBC mock을 테스트용으로 초기화한다.
    void setUp() {
        jdbc = mock(JdbcTemplate.class);
        controller = new AdminMileageController(jdbc);
        admin = new Admin();
        admin.setAdmin_id(7L);
    }

    // 관리자 마일리지 등록 요청의 테스트 데이터를 생성한다.
    private AdminMileageController.MileageCreateRequest request(String type, long amount) {
        var request = new AdminMileageController.MileageCreateRequest();
        request.officeId = 12L;
        request.mileageTypeCode = type;
        request.amount = amount;
        request.description = "테스트";
        return request;
    }

    // 잠금 대상 사무실이 존재하는 조회 결과를 mock으로 준비한다.
    private void existingOffice() {
        when(jdbc.queryForList(contains("FOR UPDATE"), eq(Long.class), eq(12L)))
                .thenReturn(List.of(12L));
    }

    @Test
    // 잔액 부족 시 사용 이력을 저장하지 않고 거절하는지 검증한다.
    void insufficientBalanceRejectsWithoutInsertingHistory() {
        // 잠금 대상 사무실이 존재하는 조회 결과를 mock으로 준비한다.
        existingOffice();
        when(jdbc.queryForObject(contains("SUM(CASE"), eq(BigDecimal.class), eq(12L)))
                .thenReturn(BigDecimal.valueOf(49));

        var error = assertThrows(ResponseStatusException.class,
                () -> controller.create(request("USE", 50), admin));

        assertEquals(HttpStatus.CONFLICT, error.getStatusCode());
        verify(jdbc, never()).update(anyString(), any(Object[].class));
    }

    @Test
    // 사무실 잠금 후 잔액을 조회하고 잔액 전액을 사용할 수 있는지 검증한다.
    void exactBalanceCanBeUsedAfterOfficeLockAndBalanceRead() {
        // 잠금 대상 사무실이 존재하는 조회 결과를 mock으로 준비한다.
        existingOffice();
        when(jdbc.queryForObject(contains("SUM(CASE"), eq(BigDecimal.class), eq(12L)))
                .thenReturn(BigDecimal.valueOf(50));
        when(jdbc.queryForObject(contains("CURRVAL"), eq(Long.class))).thenReturn(99L);

        var response = controller.create(request("USE", 50), admin);

        assertEquals(-50L, response.get("amount"));
        var order = inOrder(jdbc);
        order.verify(jdbc).queryForList(contains("FOR UPDATE"), eq(Long.class), eq(12L));
        order.verify(jdbc).queryForObject(contains("THEN -ABS(amount)"), eq(BigDecimal.class), eq(12L));
        order.verify(jdbc).update(contains("INSERT INTO mileage_history"),
                eq("USE"), eq(-50L), eq(7L), eq("테스트"), eq(12L));
    }

    @Test
    // 적립 요청은 기존 마일리지 잔액 없이 처리되는지 검증한다.
    void rewardDoesNotRequireExistingBalance() {
        // 잠금 대상 사무실이 존재하는 조회 결과를 mock으로 준비한다.
        existingOffice();
        when(jdbc.queryForObject(contains("CURRVAL"), eq(Long.class))).thenReturn(99L);

        assertEquals(50L, controller.create(request("ADMIN_REWARD", 50), admin).get("amount"));

        verify(jdbc, never()).queryForObject(anyString(), eq(BigDecimal.class), eq(12L));
    }

    @Test
    // 대상 사무실이 없으면 이력 저장 없이 404를 반환하는지 검증한다.
    void missingOfficeReturnsNotFoundWithoutHistoryWrite() {
        when(jdbc.queryForList(contains("FOR UPDATE"), eq(Long.class), eq(12L))).thenReturn(List.of());

        var error = assertThrows(ResponseStatusException.class,
                () -> controller.create(request("USE", 50), admin));

        assertEquals(HttpStatus.NOT_FOUND, error.getStatusCode());
        verify(jdbc, never()).update(anyString(), any(Object[].class));
    }

    @Test
    // 잘못된 금액과 미인증 요청이 DB에 접근하지 않는지 검증한다.
    void invalidAmountAndUnauthenticatedRequestNeverReachDatabase() {
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class,
                () -> controller.create(request("USE", 0), admin)).getStatusCode());
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                () -> controller.create(request("USE", 50), null)).getStatusCode());
        verifyNoInteractions(jdbc);
    }
}
