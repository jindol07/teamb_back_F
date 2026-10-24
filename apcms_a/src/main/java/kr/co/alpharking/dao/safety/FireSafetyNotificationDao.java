package kr.co.alpharking.dao.safety;

import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** Oracle 11g 호환 조회. NOTIFICATION의 기존 데이터를 읽기만 합니다. */
@Repository
public class FireSafetyNotificationDao {
    private final JdbcTemplate jdbc;

    public FireSafetyNotificationDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Map<String, Object>> recentByAdmin(long adminId, int limit) {
        return jdbc.queryForList("""
            SELECT * FROM (
                SELECT n.NOTIFICATION_ID, n.ADMIN_ID, n.SAFETY_INCIDENT_ID,
                       n.NOTIFICATION_TYPE_CODE, n.TITLE, n.CONTENT,
                       n.READ_YN, n.CREATED_AT, n.READ_AT
                  FROM NOTIFICATION n
                 WHERE n.ADMIN_ID = ?
                   AND n.NOTIFICATION_TYPE_CODE = 'SAFETY_INCIDENT'
                   AND n.SAFETY_INCIDENT_ID IS NOT NULL
                 ORDER BY n.CREATED_AT DESC, n.NOTIFICATION_ID DESC
            ) WHERE ROWNUM <= ?
            """, adminId, limit);
    }
}
