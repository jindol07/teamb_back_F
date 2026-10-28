package kr.co.alpharking.dao.safety;

import static org.junit.jupiter.api.Assertions.*;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

class FireSafetyTimeZoneTest {
    // 1. 업무 DB에 쓰지 않고 DAO가 실제 전달하는 SQL과 바인딩 값을 확인합니다.
    private record Statement(String sql, Object[] args) {}
    private static class RecordingJdbc extends JdbcTemplate {
        final List<Statement> statements = new ArrayList<>();
        @Override public int update(String sql, Object... args) {
            statements.add(new Statement(sql, args));
            return 1;
        }
        void assertKoreanTime(int expectedWrites) {
            assertEquals(expectedWrites, statements.size());
            for (var statement : statements) {
                assertFalse(statement.sql().contains("SYSDATE"), statement.sql());
                assertTrue(statement.sql().contains(
                    "CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS DATE)"), statement.sql());
                assertEquals(statement.args().length,
                    statement.sql().chars().filter(c -> c == '?').count(), statement.sql());
            }
        }
    }

    @Test void detectionIncidentAndNotificationUseSameBusinessTimeZone() {
        var jdbc = new RecordingJdbc();
        var dao = new FireSafetyDao(jdbc);
        var detected = Timestamp.valueOf("2026-10-28 20:37:01");
        dao.insertDetection(1, "hash", detected, "SMOKE", new BigDecimal("0.33"),
            "MEDIUM", 1, 2, "{}");
        dao.insertIncident(2, "group", 1, "SMOKE", "MEDIUM", detected);
        dao.updateIncident(2, 1, "MEDIUM", detected);
        dao.createNotifications(2, "SAFETY_INCIDENT", "시험", "내용", "ACTIVE");
        jdbc.assertKoreanTime(4);
        assertSame(detected, jdbc.statements.get(0).args()[2]);
    }

    @Test void acknowledgementAndResolutionKeepFirstAcknowledgement() {
        var jdbc = new RecordingJdbc();
        var dao = new FireSafetyWorkflowDao(jdbc);
        dao.changeOpenStatus(2, 3, "PROCESSING");
        dao.resolve(2, 3, "현장 확인");
        jdbc.assertKoreanTime(2);
        for (var statement : jdbc.statements) {
            assertTrue(statement.sql().contains("ACKNOWLEDGED_AT = NVL(ACKNOWLEDGED_AT,"));
        }
        assertEquals(2L, jdbc.statements.get(1).args()[3]);
    }

    @Test void readTimeKeepsOwnershipAndUnreadGuards() {
        var jdbc = new RecordingJdbc();
        new FireSafetyAdminInteractionDao(jdbc).markOwnNotificationRead(41, 3);
        jdbc.assertKoreanTime(1);
        var statement = jdbc.statements.get(0);
        assertTrue(statement.sql().contains("ADMIN_ID = ?"));
        assertTrue(statement.sql().contains("READ_YN = 'N'"));
        assertTrue(statement.sql().contains("NOTIFICATION_TYPE_CODE = 'SAFETY_INCIDENT'"));
        assertArrayEquals(new Object[] {41L, 3L}, statement.args());
    }
}
