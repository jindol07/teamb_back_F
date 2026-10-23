/** [1023_1010] 파일 안내
 * 용도: JDBC로 사용자 구획 현황을 읽고 유효 예약을 표시 상태에 반영.
 * 사용처·연결: ParkingSpaceQueryService.findAll → JdbcTemplate → ParkingSpacePublicRow.
 * CASE/EXISTS는 반환 상태만 계산한다. 구획 DB 상태를 수정하지 않으며 사용중·사용불가를 예약으로 덮어쓰지 않는다.
 */
package kr.co.alpharking.repository.parking;

import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;

/** 기존 테이블을 조회만 한다. 주차현황 조회용 JPA Entity나 스키마 변경은 추가하지 않는다. */
@Repository
public class ParkingSpaceQueryRepository {
    private final JdbcTemplate jdbc;

    public ParkingSpaceQueryRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    // [1023_1010] 현재 시각에 유효한 확정 예약을 비어 있는 구획의 반환 상태에만 반영한다. 원본 상태 UPDATE는 없다.
    public List<ParkingSpacePublicRow> findAll() {
        // A의 사용자용 조회와 같은 컬럼/정렬을 사용하며 Oracle 11g SQL을 유지한다.
        // [1023_1010] SQL 컬럼을 record 생성자 순서로 매핑한다. 메모·차량번호는 조회 대상에 넣지 않는다.
        return jdbc.query("""
                SELECT s.PARKING_SPACE_ID AS parkingSpaceId,
                       f.FLOOR_NO AS floorNo,
                       f.FLOOR_NAME AS floorName,
                       z.ZONE_CODE AS zoneCode,
                       s.SPACE_NUMBER AS spaceNumber,
                       s.SPACE_TYPE_CODE AS spaceTypeCode,
                       CASE
                           WHEN s.SPACE_STATUS_CODE IN ('AVAILABLE', 'EMPTY')
                            AND EXISTS (
                                SELECT 1
                                  FROM PARKING_RESERVATION r
                                 WHERE r.PARKING_SPACE_ID = s.PARKING_SPACE_ID
                                   AND r.STATUS_CODE = 'CONFIRMED'
                                   AND r.RESERVATION_START_AT <= SYSDATE
                                   AND r.RESERVATION_END_AT >= SYSDATE
                            ) THEN 'RESERVED'
                           ELSE s.SPACE_STATUS_CODE
                       END AS spaceStatusCode,
                       s.X_POSITION AS xPosition,
                       s.Y_POSITION AS yPosition,
                       s.WIDTH AS width,
                       s.HEIGHT AS height,
                       (TO_CHAR(f.FLOOR_NO) || 'F-' || z.ZONE_CODE || s.SPACE_NUMBER) AS spaceCode,
                       TO_CHAR(s.UPDATED_AT, 'YYYY-MM-DD"T"HH24:MI:SS') AS updatedAt
                  FROM PARKING_SPACE s
                  JOIN PARKING_ZONE z ON z.PARKING_ZONE_ID = s.PARKING_ZONE_ID
                  JOIN PARKING_FLOOR f ON f.PARKING_FLOOR_ID = z.PARKING_FLOOR_ID
                 ORDER BY f.FLOOR_NO, z.ZONE_CODE, s.SPACE_NUMBER
                """, (rs, rowNum) -> new ParkingSpacePublicRow(
                rs.getLong("parkingSpaceId"),
                rs.getInt("floorNo"),
                rs.getString("floorName"),
                rs.getString("zoneCode"),
                rs.getString("spaceNumber"),
                rs.getString("spaceTypeCode"),
                rs.getString("spaceStatusCode"),
                rs.getBigDecimal("xPosition"),
                rs.getBigDecimal("yPosition"),
                rs.getBigDecimal("width"),
                rs.getBigDecimal("height"),
                rs.getString("spaceCode"),
                rs.getString("updatedAt")));
    }
}
