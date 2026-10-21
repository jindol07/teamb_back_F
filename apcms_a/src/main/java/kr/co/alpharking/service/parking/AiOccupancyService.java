package kr.co.alpharking.service.parking;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dao.parking.AiOccupancyDao;
import kr.co.alpharking.dao.parking.ParkingSpaceDao;
import kr.co.alpharking.dto.parking.AiOccupancyRequest;
import kr.co.alpharking.dto.parking.AiOccupancyResponse;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.websocket.parking.ParkingSpaceChangedEvent;

@Service
public class AiOccupancyService {
    private static final Pattern CODE = Pattern.compile("[1-9][0-9]*F-[A-Z][0-9]{2,}");
    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private final AiOccupancyDao dao;
    private final ApplicationEventPublisher events;
    private final ParkingSpaceDao spaces;

    public AiOccupancyService(AiOccupancyDao dao, ApplicationEventPublisher events, ParkingSpaceDao spaces) {
        this.dao = dao;
        this.events = events;
        this.spaces = spaces;
    }

    @Transactional
    public AiOccupancyResponse receive(AiOccupancyRequest req) {
        if (req == null || req.eventId() == null || req.spaceCode() == null ||
            req.status() == null || req.detectedAt() == null || req.changeRatio() == null ||
            !"PARKING_OCCUPANCY".equals(req.eventType()) || !"AI".equals(req.source()) ||
            !CODE.matcher(req.spaceCode()).matches() ||
            !("OCCUPIED".equals(req.status()) || "AVAILABLE".equals(req.status())) ||
            req.changeRatio().compareTo(BigDecimal.ZERO) < 0 ||
            req.changeRatio().compareTo(BigDecimal.ONE) > 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "점유 이벤트 필드를 확인하세요.");
        }
        try { UUID.fromString(req.eventId()); }
        catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "event_id는 UUID여야 합니다.");
        }
        final LocalDateTime detected;
        try { detected = OffsetDateTime.parse(req.detectedAt()).atZoneSameInstant(KST).toLocalDateTime(); }
        catch (DateTimeParseException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "detected_at에는 타임존 오프셋이 필요합니다.");
        }
        ParkingSpaceRow space = dao.lockByCode(req.spaceCode());
        if (space == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "등록되지 않은 space_code입니다.");
        }
        Long id = space.getParkingSpaceId();
        String previous = space.getSpaceStatusCode();
        String needle = "\"event_id\":\"" + req.eventId() + "\"";
        if (dao.countEventId(id, needle) > 0) {
            return new AiOccupancyResponse(req.eventId(), req.spaceCode(), "DUPLICATE", previous, previous, null);
        }
        LocalDateTime last = dao.latestOccupancyDetectedAt(id);
        if (last != null && !detected.isAfter(last)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 더 최신 점유 이벤트가 처리되었습니다.");
        }
        // 제한된 필드만 검증/직렬화해 CLOB 탐색 키를 일관되게 보존한다.
        String raw = String.format(Locale.ROOT,
            "{\"event_id\":\"%s\",\"event_type\":\"PARKING_OCCUPANCY\",\"detected_at\":\"%s\",\"space_code\":\"%s\",\"status\":\"%s\",\"change_ratio\":%s,\"source\":\"AI\"}",
            req.eventId(), req.detectedAt(), req.spaceCode(), req.status(), req.changeRatio().toPlainString());
        Map<String,Object> params = new HashMap<>();
        params.put("parkingSpaceId", id);
        params.put("detectedAt", detected);
        params.put("rawPayload", raw);
        if (dao.insertEvent(params) != 1) throw new IllegalStateException("AI 이벤트 저장 실패");
        Long eventId = ((Number) params.get("aiDetectionEventId")).longValue();

        // 일회성 보정 이전(동일 초 포함)의 지연 감지는 기록만 남긴다. 새 감지는 계속 반영한다.
        java.sql.Timestamp correctedAt = spaces.latestAdminChangedAt(id);
        if (correctedAt != null && !detected.isAfter(correctedAt.toLocalDateTime())) {
            return new AiOccupancyResponse(req.eventId(), req.spaceCode(), "SKIPPED_BEFORE_CORRECTION", previous, previous, eventId);
        }

        // 예약/사용불가 상태는 AI가 임의로 덮어쓰지 않는다.
        if ("RESERVED".equals(previous) || "DISABLED".equals(previous)) {
            return new AiOccupancyResponse(req.eventId(), req.spaceCode(), "SKIPPED_PROTECTED", previous, previous, eventId);
        }
        if (previous.equals(req.status())) {
            return new AiOccupancyResponse(req.eventId(), req.spaceCode(), "UNCHANGED", previous, previous, eventId);
        }
        if (dao.updateStatus(id, req.status()) != 1) throw new IllegalStateException("주차 상태 변경 실패");
        dao.closeHistory(id);
        if (dao.insertHistory(id, eventId) != 1) throw new IllegalStateException("AI 변경 이력 기록 실패");
        events.publishEvent(new ParkingSpaceChangedEvent());
        return new AiOccupancyResponse(req.eventId(), req.spaceCode(), "UPDATED", previous, req.status(), eventId);
    }
}
