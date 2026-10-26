package kr.co.alpharking.service.safety;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/** DB 변경 없이 업무 상태/해결 메모 검증 규칙만 테스트합니다. */
class FireSafetyWorkflowServiceTest {
    @Test
    void allowedTransitions() {
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("RECEIVED", "PROCESSING"));
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("RECEIVED", "HOLD"));
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("PROCESSING", "RESOLVED"));
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("HOLD", "RESOLVED"));
    }

    @Test
    void resolvedIsFinalAndNoSkippingProcessing() {
        ResponseStatusException first = assertThrows(ResponseStatusException.class,
                () -> FireSafetyWorkflowService.validateTransition("RECEIVED", "RESOLVED"));
        assertEquals(HttpStatus.CONFLICT, first.getStatusCode());
        ResponseStatusException second = assertThrows(ResponseStatusException.class,
                () -> FireSafetyWorkflowService.validateTransition("RESOLVED", "PROCESSING"));
        assertEquals(HttpStatus.CONFLICT, second.getStatusCode());
    }

    @Test
    void resolvedRequiresNoteAndLimitsBytes() {
        ResponseStatusException blank = assertThrows(ResponseStatusException.class,
                () -> FireSafetyWorkflowService.validateRequest(2L, 2L, "RESOLVED", " "));
        assertEquals(HttpStatus.BAD_REQUEST, blank.getStatusCode());
        ResponseStatusException tooLong = assertThrows(ResponseStatusException.class,
                () -> FireSafetyWorkflowService.validateRequest(2L, 2L, "RESOLVED", "가".repeat(200)));
        assertEquals(HttpStatus.BAD_REQUEST, tooLong.getStatusCode());
        assertEquals("현장 점검 완료", FireSafetyWorkflowService.validateRequest(2L, 2L, "RESOLVED", " 현장 점검 완료 "));
    }

    @Test
    void ordinaryStatusMustNotCarryResolutionNote() {
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateRequest(2L, 2L, "PROCESSING", null));
        ResponseStatusException invalid = assertThrows(ResponseStatusException.class,
                () -> FireSafetyWorkflowService.validateRequest(2L, 2L, "PROCESSING", "메모"));
        assertEquals(HttpStatus.BAD_REQUEST, invalid.getStatusCode());
    }
}
