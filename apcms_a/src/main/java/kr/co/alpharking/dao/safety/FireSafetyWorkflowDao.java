package kr.co.alpharking.dao.safety;

import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** Oracle 행 잠금으로 같은 사건의 동시 상태 변경을 직렬화합니다. */
@Repository
public class FireSafetyWorkflowDao {
    // 1. 감지 시각과 같은 한국 시간으로 저장합니다. DB 서버의 UTC 설정에 의존하지 않습니다.
    private final JdbcTemplate jdbc;

    public FireSafetyWorkflowDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public String lockCurrentStatus(long incidentId) {
        List<String> rows = jdbc.query("""
                SELECT INCIDENT_STATUS_CODE
                  FROM SAFETY_INCIDENT
                 WHERE SAFETY_INCIDENT_ID = ?
                   FOR UPDATE
                """, (rs, row) -> rs.getString(1), incidentId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    /** ACK 담당자와 시각은 최초 변경 시에만 기록하고 덮어쓰지 않습니다. */
    public int changeOpenStatus(long incidentId, long adminId, String status) {
        return jdbc.update("""
                UPDATE SAFETY_INCIDENT
                   SET INCIDENT_STATUS_CODE = ?,
                       ACKNOWLEDGED_BY_ADMIN_ID = NVL(ACKNOWLEDGED_BY_ADMIN_ID, ?),
                       ACKNOWLEDGED_AT = NVL(ACKNOWLEDGED_AT, CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS DATE)),
                       UPDATED_AT = CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS DATE)
                 WHERE SAFETY_INCIDENT_ID = ?
                """, status, adminId, incidentId);
    }

    /** 해결 담당자/시각/메모는 RESOLVED 전환과 동일한 트랜잭션에서 저장합니다. */
    public int resolve(long incidentId, long adminId, String note) {
        return jdbc.update("""
                UPDATE SAFETY_INCIDENT
                   SET INCIDENT_STATUS_CODE = 'RESOLVED',
                       ACKNOWLEDGED_BY_ADMIN_ID = NVL(ACKNOWLEDGED_BY_ADMIN_ID, ?),
                       ACKNOWLEDGED_AT = NVL(ACKNOWLEDGED_AT, CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS DATE)),
                       RESOLVED_BY_ADMIN_ID = ?,
                       RESOLVED_AT = CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS DATE),
                       RESOLUTION_NOTE = ?,
                       UPDATED_AT = CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS DATE)
                 WHERE SAFETY_INCIDENT_ID = ?
                """, adminId, adminId, note, incidentId);
    }

    public Map<String, Object> current(long incidentId) {
        return jdbc.queryForMap("""
                SELECT SAFETY_INCIDENT_ID,
                       INCIDENT_TYPE_CODE,
                       INCIDENT_STATUS_CODE,
                       ACKNOWLEDGED_BY_ADMIN_ID,
                       ACKNOWLEDGED_AT,
                       RESOLVED_BY_ADMIN_ID,
                       RESOLVED_AT,
                       RESOLUTION_NOTE,
                       UPDATED_AT
                  FROM SAFETY_INCIDENT
                 WHERE SAFETY_INCIDENT_ID = ?
                """, incidentId);
    }
}
