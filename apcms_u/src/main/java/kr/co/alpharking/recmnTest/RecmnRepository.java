package kr.co.alpharking.recmnTest;

import java.time.LocalDateTime;
import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface RecmnRepository extends JpaRepository<PrkUsage, Long> {

    // 사용자별 과거 주차이력 조회
    @Query(value = """
        SELECT
            pu.parking_usage_id AS usage_id,
            pu.office_id AS office_id,
            TO_CHAR(pu.entry_at, 'YYYY-MM-DD HH24:MI:SS') AS usage_date,
            pz.zone_code AS target_zone
        FROM parking_usage pu
        INNER JOIN parking_space ps
            ON pu.parking_space_id = ps.parking_space_id
        INNER JOIN parking_zone pz
            ON ps.parking_zone_id = pz.parking_zone_id
        WHERE pu.office_id = :officeId
          AND pu.entry_at < SYSDATE
          AND pu.exit_at IS NOT NULL
          AND pz.zone_code IN ('A', 'B', 'C')
        ORDER BY
            pu.entry_at ASC,
            pu.parking_usage_id ASC
        """, nativeQuery = true)
    List<Object[]> getPrkPastHisById(@Param("officeId") Long officeId);

    // 사용자별 층 이용 횟수 조회
    @Query(value = """
        SELECT
            f.floor_no,
            COUNT(*) AS usage_count
        FROM parking_usage pu
        INNER JOIN parking_space ps
            ON pu.parking_space_id = ps.parking_space_id
        INNER JOIN parking_zone pz
            ON ps.parking_zone_id = pz.parking_zone_id
        INNER JOIN parking_floor f
            ON pz.parking_floor_id = f.parking_floor_id
        WHERE pu.office_id = :officeId
          AND pu.entry_at < SYSDATE
          AND pu.exit_at IS NOT NULL
          AND pz.zone_code IN ('A', 'B', 'C')
        GROUP BY f.floor_no
        ORDER BY f.floor_no
        """, nativeQuery = true)
    List<Object[]> findPastUsageCountByFloor(@Param("officeId") Long officeId);

    // 선택한 기간에 확정 예약이나 현재 주차 이용이 없는 공간 조회
    @Query(value = """
        SELECT
            s.parking_space_id,
            f.floor_no,
            z.zone_code,
            s.space_number
        FROM parking_space s
        INNER JOIN parking_zone z
            ON z.parking_zone_id = s.parking_zone_id
        INNER JOIN parking_floor f
            ON f.parking_floor_id = z.parking_floor_id
        WHERE s.space_status_code = 'AVAILABLE'
          AND z.zone_code IN ('A', 'B', 'C')
          AND NOT EXISTS (
              SELECT 1
              FROM parking_reservation r
              WHERE r.parking_space_id = s.parking_space_id
                AND r.status_code = 'CONFIRMED'
                AND r.reservation_start_at <= :endAt
                AND r.reservation_end_at >= :startAt
          )
          AND NOT EXISTS (
              SELECT 1
              FROM parking_usage u
              WHERE u.parking_space_id = s.parking_space_id
                AND u.exit_at IS NULL
          )
        ORDER BY
            f.floor_no,
            z.zone_code,
            s.space_number
        """, nativeQuery = true)
    List<Object[]> findAvailableSpaces(
            @Param("startAt") LocalDateTime startAt,
            @Param("endAt") LocalDateTime endAt
    );
}
