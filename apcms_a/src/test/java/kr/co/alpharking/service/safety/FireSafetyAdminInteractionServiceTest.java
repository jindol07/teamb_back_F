package kr.co.alpharking.service.safety;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.LinkedHashMap;
import java.util.Map;
import kr.co.alpharking.dao.safety.FireSafetyAdminInteractionDao;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/** 1. Oracle 연결 없이 서비스 업무 규칙을 검증합니다. STS Run As > JUnit Test. */
class FireSafetyAdminInteractionServiceTest {
    /** 1-1. 실제 SQL을 호출하지 않는 인메모리 DAO 대역입니다. */
    static class FakeDao extends FireSafetyAdminInteractionDao {
        String readYn = "N";
        int writes;
        int ownerAdminId = 2;
        int notificationId = 8;
        int incidentId = 2;
        String readAt = null;
        String incidentStatus = "RECEIVED";

        FakeDao() { super(null); }

        @Override
        public Map<String, Object> incidentDetail(long id) {
            if (id != incidentId) return null;
            return Map.of("SAFETY_INCIDENT_ID", id, "INCIDENT_STATUS_CODE", incidentStatus);
        }

        @Override
        public String lockOwnNotificationReadStatus(long id, long adminId) {
            return id == notificationId && adminId == ownerAdminId ? readYn : null;
        }

        @Override
        public int markOwnNotificationRead(long id, long adminId) {
            if (id != notificationId || adminId != ownerAdminId || !"N".equals(readYn)) return 0;
            readYn = "Y";
            readAt = "FIRST_READ_AT";
            writes++;
            return 1;
        }

        @Override
        public Map<String, Object> ownNotification(long id, long adminId) {
            if (id != notificationId || adminId != ownerAdminId) return null;
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("NOTIFICATION_ID", id);
            row.put("ADMIN_ID", adminId);
            row.put("READ_YN", readYn);
            row.put("READ_AT", readAt);
            return row;
        }
    }

    /** 2. 첫 번째 읽음 처리에서는 N -> Y, 첫 읽음 시각 1회 기록. */
    @Test
    void markReadOnce() {
        FakeDao dao = new FakeDao();
        FireSafetyAdminInteractionService service = new FireSafetyAdminInteractionService(dao);
        Map<String, Object> actual = service.readNotification(8L, 2L);
        assertEquals("Y", actual.get("READ_YN"));
        assertEquals(1, dao.writes);
        assertNotNull(actual.get("READ_AT"));
        assertEquals("RECEIVED", dao.incidentStatus); // 사건 상태는 변경하지 않음
    }

    /** 3. 이미 읽은 알림을 반복 호출해도 변경 건수와 읽은 시각은 유지. */
    @Test
    void repeatedReadIsIdempotent() {
        FakeDao dao = new FakeDao();
        FireSafetyAdminInteractionService service = new FireSafetyAdminInteractionService(dao);
        service.readNotification(8L, 2L);
        Map<String, Object> again = service.readNotification(8L, 2L);
        assertEquals("Y", again.get("READ_YN"));
        assertEquals("FIRST_READ_AT", again.get("READ_AT"));
        assertEquals(1, dao.writes);
    }

    /** 4. 다른 관리자의 알림은 존재 유무와 관계없이 404로 숨김. */
    @Test
    void otherAdminCannotMarkRead() {
        FakeDao dao = new FakeDao();
        FireSafetyAdminInteractionService service = new FireSafetyAdminInteractionService(dao);
        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> service.readNotification(8L, 3L));
        assertEquals(HttpStatus.NOT_FOUND, ex.getStatusCode());
        assertEquals(0, dao.writes);
    }

    /** 5. 존재하지 않는 사건/알림에 404, 잘못된 ID에 400. */
    @Test
    void invalidIdentifiersAreRejected() {
        FireSafetyAdminInteractionService service = new FireSafetyAdminInteractionService(new FakeDao());
        assertEquals(HttpStatus.NOT_FOUND, assertThrows(ResponseStatusException.class,
                () -> service.incidentDetail(9999L)).getStatusCode());
        assertEquals(HttpStatus.NOT_FOUND, assertThrows(ResponseStatusException.class,
                () -> service.readNotification(9999L, 2L)).getStatusCode());
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class,
                () -> service.incidentDetail(0L)).getStatusCode());
        assertEquals(HttpStatus.BAD_REQUEST, assertThrows(ResponseStatusException.class,
                () -> service.readNotification(-1L, 2L)).getStatusCode());
    }

    /** 6. 정상 사건 상세 조회는 상태를 변경하지 않습니다. */
    @Test
    void incidentDetailIsReadOnly() {
        FakeDao dao = new FakeDao();
        FireSafetyAdminInteractionService service = new FireSafetyAdminInteractionService(dao);
        assertEquals("RECEIVED", service.incidentDetail(2L).get("INCIDENT_STATUS_CODE"));
        assertEquals(0, dao.writes);
    }

    /** 7. 읽음 상태 판단 규칙. */
    @Test
    void readStateRules() {
        assertTrue(FireSafetyAdminInteractionService.shouldMarkRead("N"));
        assertFalse(FireSafetyAdminInteractionService.shouldMarkRead("Y"));
        assertThrows(IllegalStateException.class,
                () -> FireSafetyAdminInteractionService.shouldMarkRead("UNKNOWN"));
    }
}
