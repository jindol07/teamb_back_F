package kr.co.alpharking.repository.reservation;

import java.time.LocalDateTime;
import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import kr.co.alpharking.entity.reservation.Reservation;

@Repository
public interface ReservationRepository
        extends JpaRepository<Reservation, Long> {

    // 전체 예약 최신순 조회
    List<Reservation> findAllByOrderByParkingReservationIdDesc();

    // 사용자별 확정 및 미만료 예약 조회
    List<Reservation> findAllByOfficeIdAndStatusCodeAndReservationEndAtGreaterThanEqualOrderByParkingReservationIdDesc(
            Long officeId, String statusCode, LocalDateTime now);

    // 동일 주차 공간의 예약 시간 중복 확인
    @Query("""
        SELECT COUNT(r)
        FROM Reservation r
        WHERE r.parkingSpaceId = :parkingSpaceId
          AND r.statusCode = 'CONFIRMED'
          AND r.reservationStartAt <= :endAt
          AND r.reservationEndAt >= :startAt
        """)
    long countOverlappingReservations(
            @Param("parkingSpaceId") Long parkingSpaceId,
            @Param("startAt") LocalDateTime startAt,
            @Param("endAt") LocalDateTime endAt
    );
}
