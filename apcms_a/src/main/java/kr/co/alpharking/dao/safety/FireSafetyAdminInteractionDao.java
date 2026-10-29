package kr.co.alpharking.dao.safety;

import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** 1. Oracle 기존 테이블만 사용하는 안전사고/알림 DAO (Oracle 11g 호환). */
@Repository
public class FireSafetyAdminInteractionDao {
    // 1. 감지 시각과 같은 한국 시간으로 저장합니다. DB 서버의 UTC 설정에 의존하지 않습니다.
    private final JdbcTemplate jdbc;

    public FireSafetyAdminInteractionDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * 2. 안전 사건 상세.
     * 2-1. 개인정보나 탐지 원본 RAW_PAYLOAD는 반환하지 않습니다.
     * 2-2. IS_TEST는 최초 탐지 이벤트에 저장된 JSON에서 계산합니다.
     */
    public Map<String, Object> incidentDetail(long incidentId) {
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT s.SAFETY_INCIDENT_ID,
                       s.PARKING_SPACE_ID,
                       s.INCIDENT_TYPE_CODE,
                       s.RISK_LEVEL_CODE,
                       s.INCIDENT_STATUS_CODE,
                       s.DETECTION_COUNT,
                       s.FIRST_DETECTED_AT,
                       s.LAST_DETECTED_AT,
                       s.FIRST_AI_DETECTION_EVENT_ID,
                       s.LATEST_AI_DETECTION_EVENT_ID,
                       s.ACKNOWLEDGED_BY_ADMIN_ID,
                       s.ACKNOWLEDGED_AT,
                       s.RESOLVED_BY_ADMIN_ID,
                       s.RESOLVED_AT,
                       s.RESOLUTION_NOTE,
                       s.CREATED_AT,
                       s.UPDATED_AT,
                       CASE WHEN DBMS_LOB.INSTR(d.RAW_PAYLOAD, '"is_test":true') > 0
                            THEN 'Y' ELSE 'N' END AS IS_TEST
                  FROM SAFETY_INCIDENT s
                  JOIN AI_DETECTION_EVENT d
                    ON d.AI_DETECTION_EVENT_ID = s.FIRST_AI_DETECTION_EVENT_ID
                 WHERE s.SAFETY_INCIDENT_ID = ?
                """, incidentId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    /**
     * 3. 알림 1건에 행 잠금을 획득합니다.
     * 3-1. 반드시 JWT의 ADMIN_ID로 범위를 제한하여 다른 관리자의 알림을 숨깁니다.
     */
    public String lockOwnNotificationReadStatus(long notificationId, long adminId) {
        List<String> rows = jdbc.query("""
                SELECT n.READ_YN
                  FROM NOTIFICATION n
                 WHERE n.NOTIFICATION_ID = ?
                   AND n.ADMIN_ID = ?
                   AND n.NOTIFICATION_TYPE_CODE = 'SAFETY_INCIDENT'
                   AND n.SAFETY_INCIDENT_ID IS NOT NULL
                 FOR UPDATE
                """, (rs, row) -> rs.getString(1), notificationId, adminId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    /** 4. 이전에 읽지 않은 알림만 갱신하고 첫 읽음 시각을 기록합니다. */
    public int markOwnNotificationRead(long notificationId, long adminId) {
        return jdbc.update("""
                UPDATE NOTIFICATION
                   SET READ_YN = 'Y', READ_AT = CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS DATE)
                 WHERE NOTIFICATION_ID = ?
                   AND ADMIN_ID = ?
                   AND NOTIFICATION_TYPE_CODE = 'SAFETY_INCIDENT'
                   AND SAFETY_INCIDENT_ID IS NOT NULL
                   AND READ_YN = 'N'
                """, notificationId, adminId);
    }

    /** 5. 처리 후에도 본인에게 속한 안전 알림만 반환합니다. */
    public Map<String, Object> ownNotification(long notificationId, long adminId) {
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT n.NOTIFICATION_ID,
                       n.ADMIN_ID,
                       n.SAFETY_INCIDENT_ID,
                       n.NOTIFICATION_TYPE_CODE,
                       n.TITLE,
                       n.CONTENT,
                       n.READ_YN,
                       n.CREATED_AT,
                       n.READ_AT
                  FROM NOTIFICATION n
                 WHERE n.NOTIFICATION_ID = ?
                   AND n.ADMIN_ID = ?
                   AND n.NOTIFICATION_TYPE_CODE = 'SAFETY_INCIDENT'
                   AND n.SAFETY_INCIDENT_ID IS NOT NULL
                """, notificationId, adminId);
        return rows.isEmpty() ? null : rows.get(0);
    }
}
