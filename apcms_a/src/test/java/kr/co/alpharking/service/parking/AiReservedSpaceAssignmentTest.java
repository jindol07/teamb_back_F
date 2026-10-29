package kr.co.alpharking.service.parking;

import java.sql.Timestamp;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.ParkingReservationRow;
import kr.co.alpharking.dto.parking.ParkingUsageRow;

/** 실제 DB를 실행하지 않고 예약 연결의 업무 분기와 저장 호출을 검사한다. */
class AiReservedSpaceAssignmentTest {
    private ParkingUsageDao dao;
    private ParkingUsageService service;
    private ParkingUsageRow current;
    private ParkingReservationRow reservation;
    private final Timestamp at = Timestamp.valueOf("2026-10-22 12:00:00");

    @BeforeEach void prepare() {
        dao = mock(ParkingUsageDao.class);
        service = new ParkingUsageService(dao);
        current = new ParkingUsageRow();
        current.setParkingUsageId(70L);
        current.setVehicleNumber("91소6408");
        current.setEntryAt("2026-10-22T11:00:00");
        reservation = new ParkingReservationRow();
        reservation.setParkingReservationId(90L);
        reservation.setParkingSpaceId(16L);
        reservation.setVehicleNumber("91소6408");
        reservation.setStatusCode("CONFIRMED");
        when(dao.lockSpaceStatus(16L)).thenReturn("OCCUPIED");
        when(dao.lockOpenUsage(70L)).thenReturn(current);
        when(dao.countActiveByPlate("91소6408")).thenReturn(1);
        when(dao.lockReservationCandidates("91소6408", 16L, at)).thenReturn(List.of(reservation));
        when(dao.assignReservedSpace(70L, 16L, 90L, "91소6408", at)).thenReturn(1);
        ParkingUsageRow saved = new ParkingUsageRow();
        saved.setParkingSpaceId(16L);
        saved.setParkingReservationId(90L);
        when(dao.findById(70L)).thenReturn(saved);
    }

    private ParkingUsageService.ReservedAssignmentResult assign() {
        return service.assignReservedForAi(70L, 16L, "91소6408", at);
    }

    private void assertHeld() {
        var result = assign();
        assertNotNull(result.conflictReason());
        assertNull(result.usage());
        verify(dao, never()).assignReservedSpace(any(), any(), any(), any(), any());
        verify(dao, never()).assignObservedSpace(any(), any(), any(), any());
        assertNull(current.getParkingSpaceId());
        assertNull(current.getParkingReservationId());
    }

    @Test void savesSpaceAndReservationTogetherInLockOrder() {
        var result = assign();
        assertNull(result.conflictReason());
        assertEquals(90L, result.usage().getParkingReservationId());
        assertFalse(result.unchanged());
        var order = inOrder(dao);
        order.verify(dao).lockSpaceStatus(16L);
        order.verify(dao).lockOpenUsage(70L);
        order.verify(dao).lockReservationCandidates("91소6408", 16L, at);
        order.verify(dao).assignReservedSpace(70L, 16L, 90L, "91소6408", at);
        verify(dao, never()).assignSpace(any(), any());
    }

    private void prepareObservedReadback() {
        var saved = new ParkingUsageRow();
        saved.setParkingUsageId(70L);
        saved.setVehicleNumber("91소6408");
        saved.setParkingSpaceId(16L);
        when(dao.findById(70L)).thenReturn(saved);
        when(dao.assignObservedSpace(70L, 16L, "91소6408", at)).thenReturn(1);
    }
    private void assertObserved(String decision) {
        prepareObservedReadback();
        var result = assign();
        assertNull(result.conflictReason());
        assertEquals(decision, result.parkingDecision());
        assertEquals(16L, result.usage().getParkingSpaceId());
        assertEquals("91소6408", result.usage().getVehicleNumber());
        assertNull(result.usage().getParkingReservationId());
        verify(dao, never()).assignReservedSpace(any(), any(), any(), any(), any());
    }
    @Test void noValidReservationLinksObservedSpace() {
        when(dao.lockReservationCandidates("91소6408", 16L, at)).thenReturn(List.of());
        assertObserved("NO_VALID_RESERVATION");
    }
    @Test void duplicateReservationsAreHeld() {
        when(dao.lockReservationCandidates("91소6408", 16L, at)).thenReturn(List.of(reservation, reservation));
        assertHeld();
    }
    @Test void anotherVehicleReservationDoesNotHideActualVehicle() {
        reservation.setVehicleNumber("30고5957"); assertObserved("NO_VALID_RESERVATION");
        assertEquals("30고5957", reservation.getVehicleNumber());
    }
    @Test void anotherSpaceReservationStillLinksActualSpace() {
        reservation.setParkingSpaceId(17L); assertObserved("WRONG_SPACE");
        assertEquals(17L, reservation.getParkingSpaceId());
    }
    @Test void canceledReservationIsHeld() { reservation.setStatusCode("CANCELED"); assertHeld(); }
    @Test void missingReservationIdIsHeld() { reservation.setParkingReservationId(null); assertHeld(); }
    @Test void emptySpaceIsHeld() { when(dao.lockSpaceStatus(16L)).thenReturn("AVAILABLE"); assertHeld(); }
    @Test void missingActiveUsageIsHeld() { when(dao.lockOpenUsage(70L)).thenReturn(null); assertHeld(); }
    @Test void duplicateActiveUsageIsHeld() { when(dao.countActiveByPlate("91소6408")).thenReturn(2); assertHeld(); }
    @Test void changedVehicleIsHeld() { current.setVehicleNumber("30고5957"); assertHeld(); }
    @Test void eventBeforeEntryIsHeld() { current.setEntryAt("2026-10-22T12:01:00"); assertHeld(); }
    @Test void adminCorrectionAtSameSecondIsHeld() {
        when(dao.latestAdminChangedAt(16L)).thenReturn(at); assertHeld();
    }
    @Test void laterObservationAfterAdminCorrectionCanMatch() {
        when(dao.latestAdminChangedAt(16L)).thenReturn(Timestamp.valueOf("2026-10-22 11:59:59"));
        assertNull(assign().conflictReason());
    }
    @Test void otherVehicleOnSpaceIsHeld() {
        when(dao.countOtherActiveOnSpace(16L, 70L)).thenReturn(1); assertHeld();
    }
    @Test void otherExistingSpaceIsPreserved() {
        current.setParkingSpaceId(17L);
        assertNotNull(assign().conflictReason());
        assertEquals(17L, current.getParkingSpaceId());
        verify(dao, never()).assignReservedSpace(any(), any(), any(), any(), any());
    }
    @Test void otherExistingReservationIsPreserved() {
        current.setParkingReservationId(91L);
        assertNotNull(assign().conflictReason());
        assertEquals(91L, current.getParkingReservationId());
        verify(dao, never()).assignReservedSpace(any(), any(), any(), any(), any());
    }
    @Test void sameObservedSpaceWithoutReservationIsUnchanged() {
        current.setParkingSpaceId(16L);
        when(dao.lockReservationCandidates("91소6408", 16L, at)).thenReturn(List.of());
        prepareObservedReadback();
        assertTrue(assign().unchanged());
        verify(dao, never()).assignReservedSpace(any(), any(), any(), any(), any());
    }
    @Test void noReservationMustNotClearExistingReservationLink() {
        current.setParkingReservationId(90L);
        when(dao.lockReservationCandidates("91소6408", 16L, at)).thenReturn(List.of());
        var result = assign();
        assertNotNull(result.conflictReason());
        assertNull(result.usage());
        verify(dao, never()).assignObservedSpace(any(), any(), any(), any());
        verify(dao, never()).assignReservedSpace(any(), any(), any(), any(), any());
        assertEquals(90L, current.getParkingReservationId());
    }
    @Test void observedUpdateConflictIsHeld() {
        when(dao.lockReservationCandidates("91소6408", 16L, at)).thenReturn(List.of());
        when(dao.assignObservedSpace(70L, 16L, "91소6408", at)).thenReturn(0);
        assertNotNull(assign().conflictReason());
        verify(dao, never()).findById(any());
    }
    @Test void observedReadbackFailureThrowsForRollback() {
        when(dao.lockReservationCandidates("91소6408", 16L, at)).thenReturn(List.of());
        prepareObservedReadback();
        when(dao.findById(70L)).thenReturn(null);
        assertThrows(IllegalStateException.class, this::assign);
    }
    @Test void sameSpaceWithoutReservationIsLinked() {
        current.setParkingSpaceId(16L);
        assertFalse(assign().unchanged());
        verify(dao).assignReservedSpace(70L, 16L, 90L, "91소6408", at);
    }
    @Test void sameSpaceAndReservationStillRevalidate() {
        current.setParkingSpaceId(16L); current.setParkingReservationId(90L);
        assertTrue(assign().unchanged());
        verify(dao).lockReservationCandidates("91소6408", 16L, at);
        verify(dao).assignReservedSpace(70L, 16L, 90L, "91소6408", at);
    }
    @Test void concurrentChangeWithZeroUpdatedRowsIsHeld() {
        when(dao.assignReservedSpace(70L, 16L, 90L, "91소6408", at)).thenReturn(0);
        assertNotNull(assign().conflictReason());
        verify(dao, never()).findById(any());
    }
    @Test void failedReadbackThrowsForTransactionRollback() {
        when(dao.findById(70L)).thenReturn(null);
        assertThrows(IllegalStateException.class, this::assign);
    }
    @Test void unexpectedUpdateCountThrowsForTransactionRollback() {
        when(dao.assignReservedSpace(70L, 16L, 90L, "91소6408", at)).thenReturn(2);
        assertThrows(IllegalStateException.class, this::assign);
    }
    @Test void manualAssignmentStillUsesOriginalPath() {
        when(dao.assignSpace(70L, 16L)).thenReturn(1);
        service.assign(70L, 16L);
        verify(dao).assignSpace(70L, 16L);
        verify(dao, never()).lockReservationCandidates(any(), any(), any());
        verify(dao, never()).assignReservedSpace(any(), any(), any(), any(), any());
    }
}
