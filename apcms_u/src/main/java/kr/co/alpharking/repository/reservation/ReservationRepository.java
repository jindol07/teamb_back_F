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

    // 선택 기간에 확정 예약이나 현재 주차 이용이 없는 공간 ID 조회
    @Query(value = """
        SELECT s.PARKING_SPACE_ID
        FROM PARKING_SPACE s
        WHERE s.SPACE_STATUS_CODE IN ('AVAILABLE', 'EMPTY')
          AND NOT EXISTS (
              SELECT 1
              FROM PARKING_RESERVATION r
              WHERE r.PARKING_SPACE_ID = s.PARKING_SPACE_ID
                AND r.STATUS_CODE = 'CONFIRMED'
                AND r.RESERVATION_START_AT <= :endAt
                AND r.RESERVATION_END_AT >= :startAt
          )
          AND NOT EXISTS (
              SELECT 1
              FROM PARKING_USAGE u
              WHERE u.PARKING_SPACE_ID = s.PARKING_SPACE_ID
                AND u.EXIT_AT IS NULL
          )
        ORDER BY s.PARKING_SPACE_ID
        """, nativeQuery = true)
    List<Long> findAvailableSpaceIds(
            @Param("startAt") LocalDateTime startAt,
            @Param("endAt") LocalDateTime endAt
    );
}
