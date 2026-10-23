package kr.co.alpharking.service.reservation;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicBoolean;
import jakarta.persistence.EntityManager;
import jakarta.persistence.LockModeType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import kr.co.alpharking.entity.reservation.Reservation;
import kr.co.alpharking.entity.reservation.ReservationHistory;
import kr.co.alpharking.repository.reservation.ReservationRepository;
import kr.co.alpharking.repository.reservation.ReservationHistoryRepository;

/** 실제 DB 없이 잠금 순서·잠금 후 재검사·생성/취소 이력 보존을 검사한다. */
class ReservationConcurrencyTest {
    private ReservationRepository repository;
    private ReservationHistoryRepository histories;
    private EntityManager em;
    private ReservationService service;
    private Reservation existing;
    private final String date = LocalDate.now().plusDays(1).toString();

    @BeforeEach void prepare() {
        repository = mock(ReservationRepository.class);
        histories = mock(ReservationHistoryRepository.class);
        em = mock(EntityManager.class);
        service = new ReservationService(repository, histories);
        ReflectionTestUtils.setField(service, "entityManager", em);
        ReflectionTestUtils.setField(service, "testOfficeId", 1L);
        when(repository.lockParkingSpace(16L)).thenReturn(16L);
        when(repository.save(any(Reservation.class))).thenAnswer(call -> {
            Reservation reservation = call.getArgument(0);
            reservation.setParkingReservationId(90L);
            return reservation;
        });
        existing = new Reservation();
        existing.setParkingReservationId(90L);
        existing.setParkingSpaceId(16L);
        existing.setOfficeId(1L);
        existing.setVehicleNumber("91소6408");
        existing.setStatusCode("CONFIRMED");
        existing.setReservationTypeCode("NORMAL");
        existing.setReservationStartAt(LocalDate.now().atStartOfDay());
        existing.setReservationEndAt(LocalDate.now().plusDays(1).atTime(23, 59, 59));
        when(repository.findSpaceIdForReservation(90L)).thenReturn(Optional.of(16L));
        when(repository.findLockedById(90L)).thenReturn(Optional.of(existing));
    }

    private void create() {
        service.createReservation(1L, 16L, null, "91소6408", "NORMAL", date, date);
    }

    @Test void creationLocksSpaceBeforeOverlapCheckAndWritesInsertHistory() {
        create();
        var order = inOrder(repository, histories);
        order.verify(repository).lockParkingSpace(16L);
        order.verify(repository).countOverlappingReservations(eq(16L), any(), any());
        order.verify(repository).save(any(Reservation.class));
        var history = ArgumentCaptor.forClass(ReservationHistory.class);
        order.verify(histories).save(history.capture());
        assertEquals("INSERT", history.getValue().getChangeTypeCode());
        assertEquals("CONFIRMED", history.getValue().getStatusCode());
        assertEquals(90L, history.getValue().getReservation().getParkingReservationId());
    }

    @Test void overlapIsReadAfterWaitingForSpaceLock() {
        var locked = new AtomicBoolean();
        when(repository.lockParkingSpace(16L)).thenAnswer(call -> { locked.set(true); return 16L; });
        when(repository.countOverlappingReservations(eq(16L), any(), any())).thenAnswer(call -> {
            assertTrue(locked.get());
            return 1L;
        });
        assertThrows(IllegalArgumentException.class, this::create);
        verify(repository, never()).save(any());
        verifyNoInteractions(histories);
    }

    @Test void missingSpacePreventsReservationCreation() {
        when(repository.lockParkingSpace(16L)).thenReturn(null);
        assertThrows(IllegalArgumentException.class, this::create);
        verify(repository, never()).countOverlappingReservations(any(), any(), any());
        verify(repository, never()).save(any());
    }

    @Test void lockFailureDoesNotWriteReservationOrHistory() {
        when(repository.lockParkingSpace(16L)).thenThrow(new IllegalStateException("잠금 실패"));
        assertThrows(IllegalStateException.class, this::create);
        verify(repository, never()).save(any());
        verifyNoInteractions(histories);
    }

    @Test void testOfficeCreationAlsoUsesSameSpaceLock() {
        service.createReservation(16L, null, "91소6408", "NORMAL", date, date);
        verify(repository).lockParkingSpace(16L);
    }

    @Test void creationKeepsExistingDateBoundaryAndPayload() {
        create();
        var reservation = ArgumentCaptor.forClass(Reservation.class);
        verify(repository).save(reservation.capture());
        assertEquals(LocalDate.parse(date).atStartOfDay(), reservation.getValue().getReservationStartAt());
        assertEquals(LocalDate.parse(date).atTime(23, 59, 59), reservation.getValue().getReservationEndAt());
        assertEquals("91소6408", reservation.getValue().getVehicleNumber());
    }

    @Test void invalidInputDoesNotAcquireLocks() {
        assertThrows(IllegalArgumentException.class,
            () -> service.createReservation(0L, 16L, null, "91소6408", "NORMAL", date, date));
        verify(repository, never()).lockParkingSpace(any());
    }

    @Test void cancelLocksSpaceBeforeReservationThenRefreshesAndChecksUsage() {
        service.cancelReservation(90L);
        var order = inOrder(repository, em, histories);
        order.verify(repository).findSpaceIdForReservation(90L);
        order.verify(repository).lockParkingSpace(16L);
        order.verify(repository).findLockedById(90L);
        order.verify(em).refresh(existing, LockModeType.PESSIMISTIC_WRITE);
        order.verify(repository).countActiveUsageForReservation(90L);
        order.verify(repository).save(existing);
        var history = ArgumentCaptor.forClass(ReservationHistory.class);
        order.verify(histories).save(history.capture());
        assertEquals("CANCELED", existing.getStatusCode());
        assertNotNull(existing.getCancelledAt());
        assertEquals("UPDATE", history.getValue().getChangeTypeCode());
        assertEquals("CANCELED", history.getValue().getStatusCode());
        verify(repository, never()).findById(any());
    }

    @Test void reservationLinkedToActiveUsageCannotBeCanceled() {
        when(repository.countActiveUsageForReservation(90L)).thenReturn(1L);
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(90L));
        assertEquals("CONFIRMED", existing.getStatusCode());
        assertNull(existing.getCancelledAt());
        verify(repository, never()).save(any());
        verifyNoInteractions(histories);
    }

    @Test void endedUsageDoesNotBlockCancellation() {
        when(repository.countActiveUsageForReservation(90L)).thenReturn(0L);
        service.cancelReservation(90L);
        assertEquals("CANCELED", existing.getStatusCode());
    }

    @Test void refreshPreventsCancelingUsingStaleEntityState() {
        doAnswer(call -> { existing.setStatusCode("CANCELED"); return null; })
            .when(em).refresh(existing, LockModeType.PESSIMISTIC_WRITE);
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(90L));
        verify(repository, never()).countActiveUsageForReservation(any());
        verify(repository, never()).save(any());
        verifyNoInteractions(histories);
    }

    @Test void cancelledTimestampAlsoPreventsRepeatedCancellation() {
        existing.setCancelledAt(LocalDateTime.now());
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(90L));
        verify(repository, never()).save(any());
    }

    @Test void repeatedCancellationDoesNotDuplicateHistory() {
        service.cancelReservation(90L);
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(90L));
        verify(repository, times(1)).save(existing);
        verify(histories, times(1)).save(any());
    }

    @Test void invalidReservationIdDoesNotReadOrLock() {
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(null));
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(0L));
        verify(repository, never()).findSpaceIdForReservation(any());
        verify(repository, never()).lockParkingSpace(any());
    }

    @Test void missingReservationDoesNotAcquireSpaceLock() {
        when(repository.findSpaceIdForReservation(90L)).thenReturn(Optional.empty());
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(90L));
        verify(repository, never()).lockParkingSpace(any());
    }

    @Test void reservationDisappearingDuringLockWaitDoesNotWrite() {
        when(repository.findLockedById(90L)).thenReturn(Optional.empty());
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(90L));
        verify(repository, never()).save(any());
        verifyNoInteractions(em);
    }

    @Test void changedReservationSpaceIsRejectedAfterRefresh() {
        doAnswer(call -> { existing.setParkingSpaceId(17L); return null; })
            .when(em).refresh(existing, LockModeType.PESSIMISTIC_WRITE);
        assertThrows(IllegalArgumentException.class, () -> service.cancelReservation(90L));
        verify(repository, never()).countActiveUsageForReservation(any());
        verify(repository, never()).save(any());
    }

    @Test void refreshFailurePreventsStatusMutation() {
        doThrow(new IllegalStateException("최신 상태 확인 실패")).when(em).refresh(existing, LockModeType.PESSIMISTIC_WRITE);
        assertThrows(IllegalStateException.class, () -> service.cancelReservation(90L));
        assertEquals("CONFIRMED", existing.getStatusCode());
        verify(repository, never()).save(any());
    }

    @Test void repositoryQueriesSharePhysicalSpaceAndExcludeEndedUsage() throws Exception {
        var spaceLock = ReservationRepository.class.getMethod("lockParkingSpace", Long.class).getAnnotation(Query.class);
        assertTrue(spaceLock.nativeQuery());
        assertEquals("SELECT PARKING_SPACE_ID FROM PARKING_SPACE WHERE PARKING_SPACE_ID = :spaceId FOR UPDATE", spaceLock.value());
        assertEquals(LockModeType.PESSIMISTIC_WRITE,
            ReservationRepository.class.getMethod("findLockedById", Long.class).getAnnotation(Lock.class).value());
        String usageQuery = ReservationRepository.class.getMethod("countActiveUsageForReservation", Long.class)
            .getAnnotation(Query.class).value();
        assertTrue(usageQuery.contains("PARKING_RESERVATION_ID = :id AND EXIT_AT IS NULL"));
        String overlap = ReservationRepository.class.getMethod("countOverlappingReservations", Long.class,
            LocalDateTime.class, LocalDateTime.class).getAnnotation(Query.class).value();
        assertTrue(overlap.contains("r.cancelledAt IS NULL"));
    }
}
