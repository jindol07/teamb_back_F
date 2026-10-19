package kr.co.alpharking.recmnTest;

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
}