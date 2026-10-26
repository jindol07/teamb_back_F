package kr.co.alpharking.dao.safety;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** Oracle 11g/21c JdbcTemplate DAO. 새 업무 테이블은 생성하지 않습니다. */
@Repository
public class FireSafetyDao {
    private final JdbcTemplate jdbc;
    public FireSafetyDao(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public record Stored(long eventId, String rawPayload) {}
    public record Incident(long id, String status, String hazard, Timestamp lastDetected) {}

    public Stored existing(String eventHash) {
        var rows = jdbc.query("""
            SELECT AI_DETECTION_EVENT_ID, RAW_PAYLOAD
              FROM AI_DETECTION_EVENT WHERE SOURCE_EVENT_HASH = ?
            """, (rs, i) -> new Stored(rs.getLong(1), rs.getString(2)), eventHash);
        return rows.isEmpty() ? null : rows.get(0);
    }
    public long nextEventId() {
        return jdbc.queryForObject("SELECT SEQ_AI_DETECTION_EVENT.NEXTVAL FROM DUAL", Long.class);
    }
    public long nextIncidentId() {
        return jdbc.queryForObject("SELECT SEQ_SAFETY_INCIDENT.NEXTVAL FROM DUAL", Long.class);
    }

    public Long latestGroupId(String groupHash) {
        var rows = jdbc.query("""
            SELECT SAFETY_INCIDENT_ID FROM (
               SELECT SAFETY_INCIDENT_ID FROM SAFETY_INCIDENT
                WHERE SOURCE_GROUP_HASH = ? ORDER BY SAFETY_INCIDENT_ID DESC
            ) WHERE ROWNUM=1
            """, (rs, i) -> rs.getLong(1), groupHash);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public void insertDetection(long eventId, String eventHash, Timestamp at, String hazard,
            BigDecimal confidence, String risk, Integer x, Integer y, String raw) {
        jdbc.update("""
            INSERT INTO AI_DETECTION_EVENT (
              AI_DETECTION_EVENT_ID, SOURCE_EVENT_HASH, DETECTED_AT, CREATED_AT,
              DETECTED_OBJECT_CODE, OBJECT_CONFIDENCE, RISK_LEVEL_CODE,
              DETECTED_X, DETECTED_Y, RAW_PAYLOAD
            ) VALUES (?, ?, ?, SYSDATE, ?, ?, ?, ?, ?, ?)
            """, eventId, eventHash, at, hazard, confidence, risk, x, y, raw);
    }

    /** 같은 영상 출처 + 객체 + 공간 그리드 + 시험 여부로 묶인 미해결 사건만 갱신합니다. */
    public Incident lockActiveGroup(String groupHash) {
        var rows = jdbc.query("""
            SELECT SAFETY_INCIDENT_ID, INCIDENT_STATUS_CODE, INCIDENT_TYPE_CODE, LAST_DETECTED_AT
              FROM SAFETY_INCIDENT
             WHERE SOURCE_GROUP_HASH = ? AND INCIDENT_STATUS_CODE <> 'RESOLVED'
             FOR UPDATE
            """, (rs, i) -> new Incident(rs.getLong(1), rs.getString(2),
                rs.getString(3), rs.getTimestamp(4)), groupHash);
        return rows.isEmpty() ? null : rows.get(0);
    }

    /**
     * 1. 같은 미해결 DB 사건에 동일한 Python incident_id의 SUSPECTED가 이미 있었는지 확인.
     * 1-1. 별도 테이블/컬럼 없이 기존 RAW_PAYLOAD 감사 기록을 이용합니다.
     * 1-2. 현재 전이 행은 먼저 INSERT되므로 currentEventId를 제외합니다.
     * 1-3. 사건 최초 탐지 ID 이후의 행만 검사하고 source_group_hash까지 일치시킵니다.
     * 1-4. Oracle 11g/21c 호환: DBMS_LOB.INSTR + ROWNUM 사용.
     */
    public boolean hasPriorSuspectedInActiveIncident(long incidentId, long currentEventId,
                                                      String groupHash, String pythonIncidentId) {
        String groupMarker = "\"source_group_hash\":\"" + groupHash + "\"";
        String incidentMarker = "\"incident_id\":\"" + pythonIncidentId + "\"";
        String statusMarker = "\"status\":\"SUSPECTED\"";
        Integer count = jdbc.queryForObject("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM AI_DETECTION_EVENT e
                 WHERE e.AI_DETECTION_EVENT_ID >= (
                       SELECT FIRST_AI_DETECTION_EVENT_ID
                         FROM SAFETY_INCIDENT
                        WHERE SAFETY_INCIDENT_ID = ?)
                   AND e.AI_DETECTION_EVENT_ID <> ?
                   AND DBMS_LOB.INSTR(e.RAW_PAYLOAD, ?) > 0
                   AND DBMS_LOB.INSTR(e.RAW_PAYLOAD, ?) > 0
                   AND DBMS_LOB.INSTR(e.RAW_PAYLOAD, ?) > 0
                   AND ROWNUM = 1
            )
            """, Integer.class, incidentId, currentEventId,
                groupMarker, incidentMarker, statusMarker);
        return count != null && count > 0;
    }

    /** RESOLVED 이전에 생성된 지연 데이터로 새 사건을 잘못 생성하지 않습니다. */
    public Timestamp lastResolvedAt(String groupHash) {
        var rows = jdbc.query("""
            SELECT RESOLVED_AT FROM (
              SELECT RESOLVED_AT FROM SAFETY_INCIDENT
               WHERE SOURCE_GROUP_HASH = ? AND INCIDENT_STATUS_CODE = 'RESOLVED'
                 AND RESOLVED_AT IS NOT NULL
               ORDER BY RESOLVED_AT DESC
            ) WHERE ROWNUM = 1
            """, (rs, i) -> rs.getTimestamp(1), groupHash);
        return rows.isEmpty() ? null : rows.get(0);
    }
    public void insertIncident(long id, String groupHash, long eventId,
            String hazard, String risk, Timestamp at) {
        jdbc.update("""
            INSERT INTO SAFETY_INCIDENT (
              SAFETY_INCIDENT_ID, SOURCE_GROUP_HASH, PARKING_SPACE_ID,
              FIRST_AI_DETECTION_EVENT_ID, LATEST_AI_DETECTION_EVENT_ID,
              INCIDENT_TYPE_CODE, RISK_LEVEL_CODE, INCIDENT_STATUS_CODE,
              DETECTION_COUNT, FIRST_DETECTED_AT, LAST_DETECTED_AT,
              CREATED_AT, UPDATED_AT
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, 'RECEIVED', 1, ?, ?, SYSDATE, SYSDATE)
            """, id, groupHash, eventId, eventId, hazard, risk, at, at);
    }
    public void updateIncident(long id, long eventId, String risk, Timestamp at) {
        jdbc.update("""
            UPDATE SAFETY_INCIDENT
               SET LATEST_AI_DETECTION_EVENT_ID = ?,
                   DETECTION_COUNT = DETECTION_COUNT + 1,
                   LAST_DETECTED_AT = ?,
                   RISK_LEVEL_CODE = CASE WHEN RISK_LEVEL_CODE='HIGH' OR ?='HIGH' THEN 'HIGH'
                                          WHEN RISK_LEVEL_CODE='MEDIUM' OR ?='MEDIUM' THEN 'MEDIUM'
                                          ELSE 'LOW' END,
                   UPDATED_AT = SYSDATE
             WHERE SAFETY_INCIDENT_ID = ?
            """, eventId, at, risk, risk, id);
    }
    public int createNotifications(long incidentId, String notificationType, String title,
                                   String content, String adminStatus) {
        return jdbc.update("""
            INSERT INTO NOTIFICATION (
              NOTIFICATION_ID, OFFICE_ID, ADMIN_ID, NOTIFICATION_TYPE_CODE,
              TITLE, CONTENT, READ_YN, CREATED_AT, SAFETY_INCIDENT_ID
            ) SELECT SEQ_NOTIFICATION.NEXTVAL, NULL, a.ADMIN_ID, ?, ?, ?, 'N', SYSDATE, ?
                FROM ADMIN a WHERE a.STATUS_CODE = ?
            """, notificationType, title, content, incidentId, adminStatus);
    }
    public List<Map<String, Object>> recent(int limit) {
        return jdbc.queryForList("""
            SELECT * FROM (
              SELECT s.SAFETY_INCIDENT_ID, s.INCIDENT_TYPE_CODE, s.RISK_LEVEL_CODE,
                     s.INCIDENT_STATUS_CODE, s.DETECTION_COUNT,
                     s.FIRST_DETECTED_AT, s.LAST_DETECTED_AT,
                     s.FIRST_AI_DETECTION_EVENT_ID, s.LATEST_AI_DETECTION_EVENT_ID,
                     CASE WHEN DBMS_LOB.INSTR(d.RAW_PAYLOAD,'"is_test":true') > 0
                          THEN 'Y' ELSE 'N' END AS IS_TEST
                FROM SAFETY_INCIDENT s
                JOIN AI_DETECTION_EVENT d
                  ON d.AI_DETECTION_EVENT_ID = s.FIRST_AI_DETECTION_EVENT_ID
               ORDER BY s.SAFETY_INCIDENT_ID DESC
            ) WHERE ROWNUM <= ?
            """, limit);
    }
}
