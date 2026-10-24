package kr.co.alpharking.service.parking;

import java.sql.Timestamp;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import kr.co.alpharking.dao.parking.ParkingSpaceDao;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpaceUpdateRequest;
import kr.co.alpharking.dto.parking.ParkingUsageRow;

/** 관리자 보정의 예약 이력과 기존 출차/잠금 경로를 실제 DB 없이 검사한다. */
class ParkingSpaceReservationCorrectionTest {
    private ParkingSpaceDao spaces;
    private ParkingUsageDao usages;
    private ParkingUsageService usageService;
    private ApplicationEventPublisher events;
    private ParkingSpaceService service;
    private ParkingSpaceRow space;
    private ParkingUsageRow usage;

    @BeforeEach void prepare() {
        spaces = mock(ParkingSpaceDao.class);
        usages = mock(ParkingUsageDao.class);
        usageService = mock(ParkingUsageService.class);
        events = mock(ApplicationEventPublisher.class);
        service = new ParkingSpaceService(spaces, events, usages, usageService);
        space = new ParkingSpaceRow();
        space.setParkingSpaceId(16L);
        space.setSpaceStatusCode("OCCUPIED");
        space.setSpaceTypeCode("NORMAL");
        space.setMemo("");
        space.setUpdatedAt("2026-10-22T11:00:00");
        usage = new ParkingUsageRow();
        usage.setParkingUsageId(70L);
        usage.setVehicleNumber("91소6408");
        usage.setParkingSpaceId(16L);
        usage.setParkingReservationId(90L);
        usage.setEntryAt("2026-10-22T10:00:00");
        when(spaces.lockForUpdate(16L)).thenReturn(space);
        when(spaces.findById(16L)).thenReturn(space);
        when(spaces.latestHistoryId(16L)).thenReturn(100L);
        when(spaces.countValidTextColumns(anyString(), anyString())).thenReturn(3);
        when(spaces.updateAdminSpace(any(), any(), any(), any())).thenReturn(1);
        when(spaces.insertAdminHistory(any(), any(), any())).thenReturn(1);
        when(usages.lockActiveOnSpace(16L)).thenReturn(List.of(usage));
        when(usages.lockOpenUsage(70L)).thenReturn(usage);
        when(usages.countActiveByPlate("91소6408")).thenReturn(1);
        when(usages.detachSpace(70L, 16L)).thenReturn(1);
        when(usages.assignSpace(70L, 16L)).thenReturn(1);
    }

    private ParkingSpaceUpdateRequest request(String action, String status, List<Long> expected) {
        return new ParkingSpaceUpdateRequest(status, "NORMAL", "보정 메모", "잘못된 연결 정정", action,
            70L, "91소6408", "2026-10-22T12:00:00", space.getSpaceStatusCode(), "NORMAL", "",
            space.getUpdatedAt(), 100L, expected);
    }

    private String audit() {
        var captor = ArgumentCaptor.forClass(String.class);
        verify(spaces).insertAdminHistory(eq(16L), eq(1L), captor.capture());
        return captor.getValue();
    }

    @Test void detachRecordsPriorReservationAndClearingWithoutExit() {
        service.updateSpace(16L, request("DETACH", "AVAILABLE", List.of(70L)), 1L);
        verify(usages).detachSpace(70L, 16L);
        verifyNoInteractions(usageService);
        assertTrue(audit().contains("예약 #90"));
        assertTrue(audit().contains("예약 연결 #90→없음"));
        var order = inOrder(spaces, usages);
        order.verify(spaces).lockForUpdate(16L);
        order.verify(usages).lockActiveOnSpace(16L);
        order.verify(usages).detachSpace(70L, 16L);
        order.verify(spaces).insertAdminHistory(eq(16L), eq(1L), anyString());
    }

    @Test void manualNewSpaceRecordsClearingStaleReservation() {
        space.setSpaceStatusCode("AVAILABLE");
        usage.setParkingSpaceId(null);
        when(usages.lockActiveOnSpace(16L)).thenReturn(List.of());
        service.updateSpace(16L, request("ASSIGN", "OCCUPIED", List.of()), 1L);
        verify(usages).assignSpace(70L, 16L);
        verify(usages, never()).assignReservedSpace(any(), any(), any(), any(), any());
        assertTrue(audit().contains("예약 연결 #90→없음(수동 연결)"));
    }

    @Test void manualNewSpaceWithoutReservationDoesNotInventOne() {
        space.setSpaceStatusCode("AVAILABLE");
        usage.setParkingSpaceId(null);
        usage.setParkingReservationId(null);
        when(usages.lockActiveOnSpace(16L)).thenReturn(List.of());
        service.updateSpace(16L, request("ASSIGN", "OCCUPIED", List.of()), 1L);
        verify(usages).assignSpace(70L, 16L);
        assertTrue(audit().contains("예약 연결 없음→없음"));
    }

    @Test void sameSpaceManualCorrectionPreservesReservation() {
        service.updateSpace(16L, request("ASSIGN", "OCCUPIED", List.of(70L)), 1L);
        verify(usages, never()).assignSpace(any(), any());
        verify(usages, never()).detachSpace(any(), any());
        assertTrue(audit().contains("예약 #90"));
        assertFalse(audit().contains("예약 연결 #90→없음"));
    }

    @Test void keepDoesNotModifyEitherUsageLink() {
        service.updateSpace(16L, request("KEEP", "OCCUPIED", List.of(70L)), 1L);
        verify(usages, never()).assignSpace(any(), any());
        verify(usages, never()).detachSpace(any(), any());
        verifyNoInteractions(usageService);
        assertTrue(audit().contains("예약 #90"));
    }

    @Test void exitKeepsLinksAsHistoryAndCallsExistingExitService() {
        service.updateSpace(16L, request("EXIT", "AVAILABLE", List.of(70L)), 1L);
        verify(usageService).exitAt(70L, Timestamp.valueOf("2026-10-22 12:00:00"));
        verify(usages, never()).detachSpace(any(), any());
        assertTrue(audit().contains("예약 연결 #90 유지(출차 이력)"));
    }

    @Test void detachWithoutReservationStillRecordsMeaningfulHistory() {
        usage.setParkingReservationId(null);
        service.updateSpace(16L, request("DETACH", "AVAILABLE", List.of(70L)), 1L);
        assertTrue(audit().contains("예약 연결 없음→없음"));
    }

    @Test void staleActiveListPreventsDetachAndHistoryWrite() {
        assertThrows(ResponseStatusException.class,
            () -> service.updateSpace(16L, request("DETACH", "AVAILABLE", List.of()), 1L));
        verify(usages, never()).detachSpace(any(), any());
        verify(spaces, never()).insertAdminHistory(any(), any(), any());
    }

    @Test void changedUsagePreventsDetachAndHistoryWrite() {
        when(usages.detachSpace(70L, 16L)).thenReturn(0);
        assertThrows(ResponseStatusException.class,
            () -> service.updateSpace(16L, request("DETACH", "AVAILABLE", List.of(70L)), 1L));
        verify(spaces, never()).insertAdminHistory(any(), any(), any());
        verifyNoInteractions(events);
    }

    @Test void historyFailureThrowsInsteadOfReportingCompletedCorrection() {
        when(spaces.insertAdminHistory(any(), any(), any())).thenReturn(0);
        assertThrows(IllegalStateException.class,
            () -> service.updateSpace(16L, request("DETACH", "AVAILABLE", List.of(70L)), 1L));
        verifyNoInteractions(events);
    }
}
