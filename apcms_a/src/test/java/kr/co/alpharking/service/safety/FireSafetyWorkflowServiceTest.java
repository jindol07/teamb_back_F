package kr.co.alpharking.service.safety;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.*;
import java.util.Map;
import kr.co.alpharking.dao.safety.FireSafetyWorkflowDao;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/** DB 변경 없이 업무 상태/해결 메모 검증 규칙만 테스트합니다. */
class FireSafetyWorkflowServiceTest {
    @Test
    void allowedTransitions() {
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("RECEIVED", "PROCESSING"));
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("RECEIVED", "HOLD"));
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("RECEIVED", "RESOLVED"));
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("PROCESSING", "RESOLVED"));
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateTransition("HOLD", "RESOLVED"));
    }

    @Test
    void resolvedIsFinal() {
        ResponseStatusException second = assertThrows(ResponseStatusException.class,
                () -> FireSafetyWorkflowService.validateTransition("RESOLVED", "PROCESSING"));
        assertEquals(HttpStatus.CONFLICT, second.getStatusCode());
    }

    @Test
    void resolvedAllowsMissingNoteAndLimitsOptionalLegacyNote() {
        assertNull(FireSafetyWorkflowService.validateRequest(2L, 2L, "RESOLVED", null));
        assertNull(FireSafetyWorkflowService.validateRequest(2L, 2L, "RESOLVED", " "));
        ResponseStatusException tooLong = assertThrows(ResponseStatusException.class,
                () -> FireSafetyWorkflowService.validateRequest(2L, 2L, "RESOLVED", "가".repeat(200)));
        assertEquals(HttpStatus.BAD_REQUEST, tooLong.getStatusCode());
        assertEquals("현장 점검 완료", FireSafetyWorkflowService.validateRequest(2L, 2L, "RESOLVED", " 현장 점검 완료 "));
    }

    @Test
    void receivedResolvesWithoutNoteAndRecordsAuthenticatedAdmin() {
        var dao = mock(FireSafetyWorkflowDao.class);
        var service = new FireSafetyWorkflowService(dao);
        when(dao.lockCurrentStatus(2L)).thenReturn("RECEIVED");
        when(dao.resolve(2L, 7L, null)).thenReturn(1);
        var saved = Map.<String, Object>of("SAFETY_INCIDENT_ID", 2L, "INCIDENT_STATUS_CODE", "RESOLVED");
        when(dao.current(2L)).thenReturn(saved);
        assertEquals(saved, service.change(2L, 7L, "RESOLVED", null));
        var order = inOrder(dao);
        order.verify(dao).lockCurrentStatus(2L);
        order.verify(dao).resolve(2L, 7L, null);
        order.verify(dao).current(2L);
        verify(dao, never()).changeOpenStatus(anyLong(), anyLong(), anyString());
    }

    @Test
    void repeatedCompletionPreservesOriginalAdminAndCompletionTime() {
        var dao = mock(FireSafetyWorkflowDao.class);
        var service = new FireSafetyWorkflowService(dao);
        when(dao.lockCurrentStatus(2L)).thenReturn("RESOLVED");
        when(dao.current(2L)).thenReturn(Map.of("INCIDENT_STATUS_CODE", "RESOLVED"));
        assertEquals("RESOLVED", service.change(2L, 7L, "RESOLVED", null).get("INCIDENT_STATUS_CODE"));
        verify(dao, never()).resolve(anyLong(), anyLong(), any());
    }

    @Test
    void ordinaryStatusMustNotCarryResolutionNote() {
        assertDoesNotThrow(() -> FireSafetyWorkflowService.validateRequest(2L, 2L, "PROCESSING", null));
        ResponseStatusException invalid = assertThrows(ResponseStatusException.class,
                () -> FireSafetyWorkflowService.validateRequest(2L, 2L, "PROCESSING", "메모"));
        assertEquals(HttpStatus.BAD_REQUEST, invalid.getStatusCode());
    }
}
