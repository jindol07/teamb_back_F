/** [1023_1010] 파일 안내
 * 용도: AI 통과·매칭 이벤트 검증 및 PROCESSED/UNCHANGED/PENDING 결과 결정.
 * 사용처·연결: AiVehicleEventController → ParkingUsageDao와 ParkingUsageService.
 * 이벤트 UUID는 형식만 검사한다. 차량 이벤트 ID를 저장하지 않으므로 점유 이벤트와 같은 UUID 기반 중복 보장은 하지 않는다.
 */
package kr.co.alpharking.service.parking;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.beans.factory.annotation.Value;
import kr.co.alpharking.dto.parking.AiSpaceReleaseRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.AiVehicleEventRequest;
import kr.co.alpharking.dto.parking.AiVehicleEventResponse;
import kr.co.alpharking.dto.parking.ParkingUsageRow;

/** No schema changes: matching validates existing reservations before updating PARKING_USAGE.
 * UUID is checked for format but NOT persisted and thus cannot guarantee replay deduplication.
 */
@Service
public class AiVehicleEventService {
    private static final Pattern PLATE = Pattern.compile("^[0-9]{2,3}[가-힣][0-9]{4}$");
    private static final Pattern SPACE = Pattern.compile("[1-9][0-9]*F-[A-Z][0-9]{2,}");
    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    @Value("${parking.ai.space-release-enabled:false}")
    private boolean spaceReleaseEnabled;
    private final ParkingUsageDao usages;
    private final ParkingUsageService usageService;

    public AiVehicleEventService(ParkingUsageDao usages, ParkingUsageService usageService) {
        this.usages = usages;
        this.usageService = usageService;
    }

    @Transactional
    // [1023_1010] 통과·매칭 이벤트를 한 처리 경로에서 검증하되 각 유형의 필수 필드 조합은 구분한다.
    public AiVehicleEventResponse receive(AiVehicleEventRequest req, String expectedType) {
        if (req == null || !expectedType.equals(req.eventType())) bad("이벤트 유형이 맞지 않습니다.");
        if (req.eventId() == null) bad("event_id가 필요합니다.");
        // [1023_1010] UUID 형식 검사다. UUID 저장·재전송 중복 기록 보장으로 해석하면 안 된다.
        try { UUID.fromString(req.eventId()); } catch (IllegalArgumentException ex) { bad("event_id는 UUID여야 합니다."); }
        String plate = req.plateNumber() == null ? "" : req.plateNumber().replaceAll("\\s+", "");
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
        // [1023_1010] 감지 시각의 오프셋을 유지해 읽는다. 실제 순간 비교와 DB 저장용 한국 시각 변환은 분리한다.
        final OffsetDateTime detectedAt;
        try { detectedAt = OffsetDateTime.parse(req.detectedAt()); }
        catch (DateTimeParseException | NullPointerException ex) { throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "detected_at은 타임존 포함 ISO-8601이어야 합니다."); }
        if (detectedAt.toInstant().isAfter(Instant.now().plusSeconds(60))) bad("미래 감지 시각은 허용되지 않습니다.");
        final Timestamp at = Timestamp.valueOf(detectedAt.atZoneSameInstant(KST).toLocalDateTime());
        String outcome = "PROCESSED";
        String detail = "정상 처리";
        // [1023_1010] 현재 열린 이용 기록으로 입차·출차·매칭의 적용 가능성을 판단한다.
        // 구획 연결에서는 중복 입차를 임의 선택하거나 조회 예외로 처리하지 않는다.
        Long usageId = "VEHICLE_SPACE_MATCH".equals(expectedType)
            ? usages.findUniqueOpenUsageByPlate(plate) : usages.findOpenUsageByPlate(plate);
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
                    // [1023_1010] 예상 배정 충돌을 예외로 던지지 않고 PENDING으로 반환한다. 이 경계를 유지해야 롤백 전용 상태를 피할 수 있다.
                var result = usageService.assignReservedForAi(usageId, spaceId, plate, at);
                if (result.conflictReason() != null) {
                    outcome = "PENDING"; detail = result.conflictReason();
                } else if (result.unchanged()) {
                    outcome = "UNCHANGED"; detail = "이미 동일 구획과 예약에 연결되어 있습니다.";
                }
            }
        }
        // [1023_1010] HTTP 성공 응답 안에서도 outcome을 확인해야 한다. PENDING은 작업 반영 완료를 뜻하지 않는다.
        Long version = null;
        if (spaceReleaseEnabled && "VEHICLE_SPACE_MATCH".equals(expectedType) && !"PENDING".equals(outcome)) {
            version = usages.lockLinkVersion(usageId);
            if (version == null || version < 0) throw new IllegalStateException("연결 버전을 조회할 수 없습니다.");
        }
        return new AiVehicleEventResponse(req.eventId(), expectedType, outcome, plate, req.spaceCode(), usageId, detail, version);
    }
    @Transactional
    public AiVehicleEventResponse release(AiSpaceReleaseRequest req) {
        if (!spaceReleaseEnabled) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "AI 구획 해제 비활성");
        if (req == null || !"VEHICLE_SPACE_RELEASE".equals(req.eventType()) || req.eventId() == null) bad("해제 이벤트 유형·ID를 확인하세요.");
        try { UUID.fromString(req.eventId()); } catch (IllegalArgumentException ex) { bad("event_id는 UUID여야 합니다."); }
        String plate = req.plateNumber() == null ? "" : req.plateNumber().replaceAll("\\s+", "");
        if (!PLATE.matcher(plate).matches() || req.cameraId() == null || req.cameraId().isBlank() || req.cameraId().length() > 60
                || req.spaceCode() == null || !SPACE.matcher(req.spaceCode()).matches()
                || req.parkingUsageId() == null || req.parkingUsageId() < 1 || req.linkVersion() == null
                || req.linkVersion() < 0 || req.linkVersion() == Long.MAX_VALUE
                || !"CONFIRMED_EMPTY".equals(req.reason())) bad("해제 차량·구획·이용·버전·근거를 확인하세요.");
        // 팀원 develop 수정과 같이 실제 순간 비교와 DB 한국 시각 저장을 분리합니다.
        final OffsetDateTime detectedAt;
        try { detectedAt = OffsetDateTime.parse(req.detectedAt()); }
        catch (DateTimeParseException | NullPointerException ex) { throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "감지 시각을 확인하세요."); }
        if (detectedAt.toInstant().isAfter(Instant.now().plusSeconds(60))) bad("미래 해제 시각은 허용되지 않습니다.");
        final Timestamp at = Timestamp.valueOf(detectedAt.atZoneSameInstant(KST).toLocalDateTime());
        Long spaceId = usages.findSpaceIdByCode(req.spaceCode());
        if (spaceId == null) return new AiVehicleEventResponse(req.eventId(), req.eventType(), "PENDING", plate,
            req.spaceCode(), req.parkingUsageId(), "기존 구획을 찾지 못했습니다.", null);
        var result = usageService.releaseForAi(req.parkingUsageId(), spaceId, plate, req.linkVersion(), at);
        return new AiVehicleEventResponse(req.eventId(), req.eventType(), result.conflictReason() == null ? "PROCESSED" : "PENDING",
            plate, req.spaceCode(), req.parkingUsageId(), result.conflictReason() == null ? "기존 구획·예약 연결 해제" : result.conflictReason(),
            result.linkVersion());
    }
    // [1023_1010] 입력 계약 위반은 처리 보류와 구분하여 HTTP 400으로 반환한다.

    private static void bad(String msg) { throw new ResponseStatusException(HttpStatus.BAD_REQUEST, msg); }
}
