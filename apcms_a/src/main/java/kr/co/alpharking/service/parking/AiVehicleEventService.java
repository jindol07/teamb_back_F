package kr.co.alpharking.service.parking;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.AiVehicleEventRequest;
import kr.co.alpharking.dto.parking.AiVehicleEventResponse;
import kr.co.alpharking.dto.parking.ParkingUsageRow;

/** No schema changes: requests are handled using PARKING_USAGE only.
 * UUID is checked for format but NOT persisted and thus cannot guarantee replay deduplication.
 */
@Service
public class AiVehicleEventService {
    private static final Pattern PLATE = Pattern.compile("^[0-9]{2,3}[가-힣][0-9]{4}$");
    private static final Pattern SPACE = Pattern.compile("[1-9][0-9]*F-[A-Z][0-9]{2,}");
    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private final ParkingUsageDao usages;
    private final ParkingUsageService usageService;

    public AiVehicleEventService(ParkingUsageDao usages, ParkingUsageService usageService) {
        this.usages = usages;
        this.usageService = usageService;
    }

    @Transactional
    public AiVehicleEventResponse receive(AiVehicleEventRequest req, String expectedType) {
        if (req == null || !expectedType.equals(req.eventType())) bad("이벤트 유형이 맞지 않습니다.");
        if (req.eventId() == null) bad("event_id가 필요합니다.");
        try { UUID.fromString(req.eventId()); } catch (IllegalArgumentException ex) { bad("event_id는 UUID여야 합니다."); }
        String plate = req.plateNumber() == null ? "" : req.plateNumber().replaceAll("\s+", "");
        if (!PLATE.matcher(plate).matches()) bad("차량번호 형식을 확인하세요.");
        if (req.cameraId() == null || req.cameraId().isBlank() || req.cameraId().length() > 60) bad("camera_id가 필요합니다.");
        if (req.confidence() == null || req.confidence().compareTo(BigDecimal.ZERO) < 0 || req.confidence().compareTo(BigDecimal.ONE) > 0) bad("confidence는 0~1이어야 합니다.");
        if ("VEHICLE_PASSAGE".equals(expectedType)) {
            if (!("ENTRY".equals(req.direction()) || "EXIT".equals(req.direction())) || req.spaceCode() != null)
                bad("direction 또는 space_code가 올바르지 않습니다.");
        } else {
            if (req.direction() != null || req.spaceCode() == null || !SPACE.matcher(req.spaceCode()).matches()
                  || !("TRACKING".equals(req.method()) || "PLATE_OCR".equals(req.method())))
                bad("주차구획 매칭 필드가 올바르지 않습니다.");
        }
        final Timestamp at;
        try { at = Timestamp.valueOf(OffsetDateTime.parse(req.detectedAt()).atZoneSameInstant(KST).toLocalDateTime()); }
        catch (DateTimeParseException | NullPointerException ex) { throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "detected_at은 타임존 포함 ISO-8601이어야 합니다."); }
        if (at.getTime() > System.currentTimeMillis() + 60_000L) bad("미래 감지 시각은 허용되지 않습니다.");
        String outcome = "PROCESSED";
        String detail = "정상 처리";
        Long usageId = usages.findOpenUsageByPlate(plate);
        if ("VEHICLE_PASSAGE".equals(expectedType)) {
            if ("ENTRY".equals(req.direction())) {
                if (usageId != null) { outcome = "UNCHANGED"; detail = "현재 입차 기록이 이미 존재합니다."; }
                else {
                    // Prevent a delayed ENTRY replay after a known EXIT. Same-second precision follows Oracle DATE.
                    Timestamp latestExit = usages.findLatestExitByPlate(plate);
                    if (latestExit != null && !at.after(latestExit)) {
                        outcome = "PENDING"; detail = "최근 출차 시각 이전의 입차 이벤트입니다.";
                    } else usageId = usageService.enterAt(plate, at).getParkingUsageId();
                }
            } else if (usageId == null) {
                outcome = "PENDING"; detail = "활성 입차 기록이 없어 출차 처리하지 않았습니다.";
            } else {
                ParkingUsageRow open = usages.findById(usageId);
                if (open == null || open.getEntryAt() == null ||
                    at.toLocalDateTime().isBefore(LocalDateTime.parse(open.getEntryAt()))) {
                    outcome = "PENDING"; detail = "입차 이전의 출차 이벤트입니다.";
                } else usageService.exitAt(usageId, at);
            }
        } else {
            Long spaceId = usages.findSpaceIdByCode(req.spaceCode());
            if (spaceId == null || usageId == null) {
                outcome = "PENDING"; detail = "주차구획 또는 활성 입차 기록을 찾지 못했습니다.";
            } else {
                ParkingUsageRow open = usages.findById(usageId);
                if (open == null || open.getEntryAt() == null ||
                    at.toLocalDateTime().isBefore(LocalDateTime.parse(open.getEntryAt()))) {
                    outcome = "PENDING"; detail = "입차 이전의 매칭 이벤트입니다.";
                } else if (spaceId.equals(open.getParkingSpaceId())) {
                    outcome = "UNCHANGED"; detail = "이미 동일 구획에 연결되어 있습니다.";
                } else {
                    var result = usageService.assignForAi(usageId, spaceId);
                    if (result.conflictReason() != null) {
                        outcome = "PENDING"; detail = result.conflictReason();
                    }
                }
            }
        }
        return new AiVehicleEventResponse(req.eventId(), expectedType, outcome, plate, req.spaceCode(), usageId, detail);
    }
    private static void bad(String msg) { throw new ResponseStatusException(HttpStatus.BAD_REQUEST, msg); }
}
