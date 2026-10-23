package kr.co.alpharking.service.safety;

import java.math.RoundingMode;
import java.sql.Timestamp;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import kr.co.alpharking.dao.safety.FireSafetyDao;
import kr.co.alpharking.dto.safety.FireSafetyRequest;
import kr.co.alpharking.dto.safety.FireSafetyResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.ObjectMapper;

/** 탐지 기록·업무 사건·알림 생성은 전부 하나의 DB 트랜잭션입니다. */
@Service
public class FireSafetyAtomicWriter {
    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private final FireSafetyDao dao;
    private final ObjectMapper mapper;
    private final String notificationType;
    private final String adminStatus;
    private final String fireRisk;
    private final String smokeRisk;

    public FireSafetyAtomicWriter(FireSafetyDao dao, ObjectMapper mapper,
            @Value("${fire.alert.notification.type:}") String notificationType,
            @Value("${fire.alert.admin.status:}") String adminStatus,
            @Value("${fire.alert.risk.fire:HIGH}") String fireRisk,
            @Value("${fire.alert.risk.smoke:MEDIUM}") String smokeRisk) {
        this.dao = dao;
        this.mapper = mapper;
        this.notificationType = notificationType;
        this.adminStatus = adminStatus;
        this.fireRisk = fireRisk;
        this.smokeRisk = smokeRisk;
    }

    public static String requestHash(FireSafetyRequest request, ObjectMapper mapper) {
        return FireSafetyGroupKey.sha256(mapper.writeValueAsString(request));
    }
    public static String correlation(FireSafetyRequest request) {
        var b = request.bboxXyxy();
        return FireSafetyGroupKey.group(request.source().kind(), request.source().name(),
            request.hazardType(), b.get(0), b.get(1), b.get(2), b.get(3), request.isTest());
    }

    @Transactional
    public FireSafetyResponse write(FireSafetyRequest r, String hash) {
        var old = dao.existing(r.transitionId());
        if (old != null) return FireSafetyIngest.duplicate(r, hash, old, dao);

        String risk = "FIRE".equals(r.hazardType()) ? fireRisk : smokeRisk;
        if (!Set.of("LOW", "MEDIUM", "HIGH").contains(risk))
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                "위험 등급 매핑을 확인하세요.");
        Timestamp detectedAt = Timestamp.valueOf(OffsetDateTime.parse(r.observedAtUtc())
                .atZoneSameInstant(KST).toLocalDateTime());
        String groupHash = correlation(r);
        Map<String, Object> audit = new LinkedHashMap<>();
        audit.put("request_hash", hash);
        audit.put("source_group_hash", groupHash);
        audit.put("received_transition", r);
        String raw = mapper.writeValueAsString(audit);

        boolean detection = !"CLEARED".equals(r.status());
        var b = r.bboxXyxy();
        int centerX = (b.get(0) + b.get(2)) / 2;
        int centerY = (b.get(1) + b.get(3)) / 2;
        long eventId = dao.nextEventId();
        // CLEARED는 정상 탐지 결과가 아닙니다. 객체·신뢰도·위험도·좌표를 NULL로 저장하는 감사행입니다.
        dao.insertDetection(eventId, r.transitionId(), detectedAt,
                detection ? r.hazardType() : null,
                detection ? r.confidence().setScale(4, RoundingMode.HALF_UP) : null,
                detection ? risk : null, detection ? centerX : null,
                detection ? centerY : null, raw);

        if (!detection || "LOW".equals(risk)) {
            // LOW는 원시 로그만 저장. CLEARED도 관리자 RESOLVED로 자동 변경하지 않음.
            return new FireSafetyResponse(r.transitionId(), "STORED", eventId, null, 0, r.isTest());
        }

        FireSafetyDao.Incident active = dao.lockActiveGroup(groupHash);
        Long incidentId;
        boolean newIncident = active == null;

        // 1. DB 업무 사건은 미해결 SOURCE_GROUP_HASH 단위로 유지합니다.
        // 1-1. 새 Python SUSPECTED는 새 incident_id를 뜻하므로, 기존 그룹에 묶여도 재알림을 보냅니다.
        // 1-2. 같은 Python incident_id의 중복 SUSPECTED는 이력에 이미 있으면 알림을 보내지 않습니다.
        // 1-3. REOPENED는 원래 정책대로 매번 재알림합니다. CLEARED는 위에서 이미 반환했습니다.
        boolean notifyAdmins = newIncident || "REOPENED".equals(r.status());
        if (!newIncident && "SUSPECTED".equals(r.status())) {
            notifyAdmins = !dao.hasPriorSuspectedInActiveIncident(
                    active.id(), eventId, groupHash, r.incidentId());
        }

        if (newIncident) {
            Timestamp lastResolved = dao.lastResolvedAt(groupHash);
            if (lastResolved != null && !detectedAt.after(lastResolved))
                throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "관리자가 해결한 시각 이전의 지연 전이입니다. 새 사건을 생성하지 않습니다.");
            incidentId = dao.nextIncidentId();
            dao.insertIncident(incidentId, groupHash, eventId, r.hazardType(), risk, detectedAt);
        } else {
            if (!r.hazardType().equals(active.hazard()))
                throw new ResponseStatusException(HttpStatus.CONFLICT, "다른 위험 유형의 활성 사건입니다.");
            if (active.lastDetected() != null && detectedAt.before(active.lastDetected()))
                throw new ResponseStatusException(HttpStatus.CONFLICT, "도착 순서가 역전된 탐지입니다.");
            incidentId = active.id();
            dao.updateIncident(incidentId, eventId, risk, detectedAt);
        }

        int notifications = 0;
        if (notifyAdmins) {
            if (notificationType.isBlank() || adminStatus.isBlank())
                throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "fire.alert.notification.type / fire.alert.admin.status 설정이 필요합니다.");
            String title = (r.isTest() ? "[TEST] " : "") + r.hazardType() + " 감지 의심";
            String content = "AI " + r.status() + " 관찰; 관리자 현장 확인 필요 (자동 해결 판정 아님)";
            notifications = dao.createNotifications(incidentId, notificationType, title, content, adminStatus);
            if (notifications <= 0)
                throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "알림 대상 관리자가 없습니다. 활성 관리자 상태 코드를 확인하세요.");
        }
        return new FireSafetyResponse(r.transitionId(), "STORED", eventId,
                incidentId, notifications, r.isTest());
    }
}
