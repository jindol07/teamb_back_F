package kr.co.alpharking.service.safety;

import static org.junit.jupiter.api.Assertions.*;
import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.co.alpharking.dao.safety.FireSafetyDao;
import kr.co.alpharking.dto.safety.FireSafetyRequest;
import kr.co.alpharking.dto.safety.FireSafetyResponse;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

/**
 * 1. DB 없이 신규 SUSPECTED 재알림 정책을 검증합니다.
 * 1-1. STS: 이 파일 우클릭 -> Run As -> JUnit Test.
 * 1-2. 실제 DBMS_LOB.INSTR SQL 실행은 Postman+SQLGate 통합 검증에서 확인합니다.
 */
class FireSafetySuspectedRenotifyTest {
    private static final ObjectMapper JSON = new ObjectMapper();

    /** 2. Oracle 대신 메모리에서 그룹/전송 중복/알림 생성 횟수를 추적합니다. */
    static class FakeDao extends FireSafetyDao {
        final Set<String> pythonSuspected = new HashSet<>();
        final Map<String, Stored> received = new HashMap<>();
        long eventId = 55;
        long nextIncidentId = 5;
        Long activeIncidentId;
        int notifications;
        int checks;
        int eventWrites;
        int incidentInserts;
        int incidentUpdates;
        boolean alwaysPretendOldSuspected;

        FakeDao() { super(null); }
        @Override public Stored existing(String hash) { return received.get(hash); }
        @Override public long nextEventId() { return ++eventId; }
        @Override public long nextIncidentId() { return nextIncidentId++; }
        @Override public Timestamp lastResolvedAt(String groupHash) { return null; }
        @Override public Incident lockActiveGroup(String groupHash) {
            if (activeIncidentId == null) return null;
            return new Incident(activeIncidentId, "RECEIVED", "FIRE", Timestamp.from(Instant.parse("2026-10-23T00:00:00Z")));
        }
        @Override public void insertIncident(long id, String groupHash, long event,
                String hazard, String risk, Timestamp at) {
            activeIncidentId = id;
            incidentInserts++;
        }
        @Override public void updateIncident(long id, long event, String risk, Timestamp at) {
            assertEquals(activeIncidentId.longValue(), id);
            incidentUpdates++;
        }
        @Override public boolean hasPriorSuspectedInActiveIncident(long id, long currentEvent,
                String group, String pythonIncidentId) {
            checks++;
            return alwaysPretendOldSuspected || pythonSuspected.contains(pythonIncidentId);
        }
        @Override public void insertDetection(long id, String transitionId, Timestamp at,
                String hazard, BigDecimal confidence, String risk, Integer x, Integer y, String raw) {
            eventWrites++;
            received.put(transitionId, new Stored(id, raw));
            // 실제 DAO는 현재 행을 검사에서 제외합니다. Fake도 검사 후 등록하는 의미를 유지.
        }
        @Override public Long latestGroupId(String groupHash) { return activeIncidentId; }
        @Override public int createNotifications(long incidentId, String type, String title,
                String content, String adminStatus) {
            notifications += 3;
            return 3;
        }
    }

    private static FireSafetyRequest request(String transitionHex, String pythonId, String status, int frame) {
        return new FireSafetyRequest("1.0", transitionHex.repeat(64), pythonId, "region-test-1",
                "FIRE", status, "2026-10-23T05:00:00+00:00", new BigDecimal(frame),
                (long) frame, new BigDecimal("0.85"), List.of(100, 100, 200, 200),
                3L, null, new FireSafetyRequest.Source("VIDEO", "fire_realert_test.mp4"),
                "2026-10-23T04:59:00+00:00", true, true);
    }
    private static FireSafetyAtomicWriter writer(FakeDao dao) {
        return new FireSafetyAtomicWriter(dao, JSON,
                "SAFETY_INCIDENT", "ACTIVE", "HIGH", "MEDIUM");
    }

    /** 3. 신규 사건에는 관리자 세 명에게 최초 알림. */
    @Test void firstSuspectedCreatesIncidentAndThreeNotifications() {
        FakeDao dao = new FakeDao();
        FireSafetyRequest first = request("a", "python-A", "SUSPECTED", 1);
        FireSafetyResponse result = writer(dao).write(first, FireSafetyAtomicWriter.requestHash(first, JSON));
        assertEquals(3, result.notificationsCreated());
        assertEquals(Long.valueOf(5L), result.safetyIncidentId());
        assertEquals(1, dao.incidentInserts);
        assertEquals(0, dao.checks);
    }

    /** 4. 동일 DB 사건에 새 Python incident_id의 SUSPECTED => 사건 갱신 + 재알림. */
    @Test void newPythonSuspectedNotifiesButDoesNotCreateAnotherBusinessIncident() {
        FakeDao dao = new FakeDao();
        dao.activeIncidentId = 5L;
        FireSafetyRequest second = request("b", "python-B", "SUSPECTED", 55);
        FireSafetyResponse result = writer(dao).write(second, FireSafetyAtomicWriter.requestHash(second, JSON));
        assertEquals(Long.valueOf(5L), result.safetyIncidentId());
        assertEquals(3, result.notificationsCreated());
        assertEquals(1, dao.checks);
        assertEquals(1, dao.incidentUpdates);
        assertEquals(0, dao.incidentInserts);
    }

    /** 5. 같은 Python incident_id의 SUSPECTED가 이미 기록됐으면 중복 재알림 금지. */
    @Test void samePythonIncidentSuspectedDoesNotRenotify() {
        FakeDao dao = new FakeDao();
        dao.activeIncidentId = 5L;
        dao.pythonSuspected.add("python-A");
        FireSafetyRequest again = request("c", "python-A", "SUSPECTED", 55);
        FireSafetyResponse result = writer(dao).write(again, FireSafetyAtomicWriter.requestHash(again, JSON));
        assertEquals(0, result.notificationsCreated());
        assertEquals(1, dao.incidentUpdates);
        assertEquals(1, dao.checks);
    }

    /** 6. 같은 Python 사건의 REOPENED는 기존처럼 3명에게 재알림. */
    @Test void reopenedStillNotifies() {
        FakeDao dao = new FakeDao();
        dao.activeIncidentId = 5L;
        dao.pythonSuspected.add("python-A");
        FireSafetyRequest reopened = request("d", "python-A", "REOPENED", 60);
        FireSafetyResponse result = writer(dao).write(reopened, FireSafetyAtomicWriter.requestHash(reopened, JSON));
        assertEquals(3, result.notificationsCreated());
        assertEquals(0, dao.checks);
    }

    /** 7. CLEARED는 DB 탐지 감사 기록만 생성하고 알림/업무 상태는 변경하지 않음. */
    @Test void clearedNeverNotifiesOrUpdatesIncident() {
        FakeDao dao = new FakeDao();
        dao.activeIncidentId = 5L;
        FireSafetyRequest cleared = request("e", "python-A", "CLEARED", 65);
        FireSafetyResponse result = writer(dao).write(cleared, FireSafetyAtomicWriter.requestHash(cleared, JSON));
        assertEquals(0, result.notificationsCreated());
        assertNull(result.safetyIncidentId());
        assertEquals(1, dao.eventWrites);
        assertEquals(0, dao.incidentUpdates);
        assertEquals(0, dao.checks);
    }

    /** 8. 정확히 같은 transition_id/본문을 재전송하면 신규 이벤트 및 알림이 없음. */
    @Test void duplicateTransitionIsIdempotent() {
        FakeDao dao = new FakeDao();
        dao.activeIncidentId = 5L;
        FireSafetyRequest first = request("f", "python-B", "SUSPECTED", 1);
        String hash = FireSafetyAtomicWriter.requestHash(first, JSON);
        FireSafetyResponse initial = writer(dao).write(first, hash);
        FireSafetyResponse repeated = writer(dao).write(first, hash);
        assertEquals("STORED", initial.outcome());
        assertEquals("DUPLICATE", repeated.outcome());
        assertEquals(0, repeated.notificationsCreated());
        assertEquals(1, dao.eventWrites);
        assertEquals(3, dao.notifications);
    }
}
