
package kr.co.alpharking.chatbot.inquiry;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDateTime;
import java.util.List;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** 챗봇 읽기 전용 조회. Office ID는 Controller에서 인증 정보로만 결정합니다. */
@Repository
public class ChatbotQueryRepository {

    private final JdbcTemplate jdbc;

    public ChatbotQueryRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public record UsageRow(
        long parkingUsageId,
        String vehicleNumber,
        String spaceCode,
        LocalDateTime entryAt,
        LocalDateTime exitAt
    ) {}

    public record ReservationRow(
        long reservationId,
        String vehicleNumber,
        String spaceCode,
        LocalDateTime startAt,
        LocalDateTime endAt,
        String statusCode
    ) {}

    public record VehicleRow(
        long vehicleId,
        String vehicleNumber,
        String vehicleModel,
        String registrationStatusCode,
        String rejectedReason
    ) {}

    // 주차 이용 내역: 최신 50건
    public List<UsageRow> findUsage(long officeId) {
        return jdbc.query("""
            SELECT *
            FROM (
                SELECT
                    u.PARKING_USAGE_ID,
                    u.VEHICLE_NUMBER,
                    u.ENTRY_AT,
                    u.EXIT_AT,
                    CASE
                        WHEN f.FLOOR_NO IS NULL THEN NULL
                        ELSE TO_CHAR(f.FLOOR_NO) || 'F-' ||
                             z.ZONE_CODE || s.SPACE_NUMBER
                    END AS SPACE_CODE
                FROM PARKING_USAGE u
                LEFT JOIN PARKING_SPACE s
                    ON s.PARKING_SPACE_ID = u.PARKING_SPACE_ID
                LEFT JOIN PARKING_ZONE z
                    ON z.PARKING_ZONE_ID = s.PARKING_ZONE_ID
                LEFT JOIN PARKING_FLOOR f
                    ON f.PARKING_FLOOR_ID = z.PARKING_FLOOR_ID
                WHERE u.OFFICE_ID = ?
                ORDER BY
                    u.ENTRY_AT DESC,
                    u.PARKING_USAGE_ID DESC
            )
            WHERE ROWNUM <= 50
            """,
            (rs, row) -> new UsageRow(
                rs.getLong("PARKING_USAGE_ID"),
                rs.getString("VEHICLE_NUMBER"),
                rs.getString("SPACE_CODE"),
                time(rs, "ENTRY_AT"),
                time(rs, "EXIT_AT")
            ),
            officeId
        );
    }

    // 예약 내역: 최신 50건
    public List<ReservationRow> findReservations(long officeId) {
        return jdbc.query("""
            SELECT *
            FROM (
                SELECT
                    r.PARKING_RESERVATION_ID,
                    r.VEHICLE_NUMBER,
                    r.RESERVATION_START_AT,
                    r.RESERVATION_END_AT,
                    r.STATUS_CODE,
                    CASE
                        WHEN f.FLOOR_NO IS NULL THEN NULL
                        ELSE TO_CHAR(f.FLOOR_NO) || 'F-' ||
                             z.ZONE_CODE || s.SPACE_NUMBER
                    END AS SPACE_CODE
                FROM PARKING_RESERVATION r
                LEFT JOIN PARKING_SPACE s
                    ON s.PARKING_SPACE_ID = r.PARKING_SPACE_ID
                LEFT JOIN PARKING_ZONE z
                    ON z.PARKING_ZONE_ID = s.PARKING_ZONE_ID
                LEFT JOIN PARKING_FLOOR f
                    ON f.PARKING_FLOOR_ID = z.PARKING_FLOOR_ID
                WHERE r.OFFICE_ID = ?
                ORDER BY
                    r.CREATED_AT DESC,
                    r.PARKING_RESERVATION_ID DESC
            )
            WHERE ROWNUM <= 50
            """,
            (rs, row) -> new ReservationRow(
                rs.getLong("PARKING_RESERVATION_ID"),
                rs.getString("VEHICLE_NUMBER"),
                rs.getString("SPACE_CODE"),
                time(rs, "RESERVATION_START_AT"),
                time(rs, "RESERVATION_END_AT"),
                rs.getString("STATUS_CODE")
            ),
            officeId
        );
    }

    // 등록 차량: 삭제되지 않은 최신 50건
    public List<VehicleRow> findVehicles(long officeId) {
        return jdbc.query("""
            SELECT *
            FROM (
                SELECT
                    VEHICLE_ID,
                    VEHICLE_NUMBER,
                    VEHICLE_MODEL,
                    REGISTRATION_STATUS_CODE,
                    REJECTED_REASON
                FROM VEHICLE
                WHERE OFFICE_ID = ?
                  AND DELETED_AT IS NULL
                ORDER BY
                    CREATED_AT DESC,
                    VEHICLE_ID DESC
            )
            WHERE ROWNUM <= 50
            """,
            (rs, row) -> new VehicleRow(
                rs.getLong("VEHICLE_ID"),
                rs.getString("VEHICLE_NUMBER"),
                rs.getString("VEHICLE_MODEL"),
                rs.getString("REGISTRATION_STATUS_CODE"),
                rs.getString("REJECTED_REASON")
            ),
            officeId
        );
    }

    private static LocalDateTime time(
        ResultSet rs,
        String column
    ) throws SQLException {
        var timestamp = rs.getTimestamp(column);
        return timestamp == null
            ? null
            : timestamp.toLocalDateTime();
    }
}
