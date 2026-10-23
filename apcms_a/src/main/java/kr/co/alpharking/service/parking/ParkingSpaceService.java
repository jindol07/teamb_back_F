/** [1023_1010] 파일 안내
 * 용도: 관리자 구획 원본·예약 조회와 기존 이용 기록 기반 일회성 보정.
 * 사용처·연결: ParkingSpaceController → ParkingSpaceDao/ParkingUsageDao; EXIT는 ParkingUsageService 사용.
 * 보정은 잠금·조회 기준 대조·이용 기록 변경·구획·이력 저장을 같은 트랜잭션에서 처리하고 변경 이벤트를 발행한다.
 */
package kr.co.alpharking.service.parking;

import java.util.List;
import kr.co.alpharking.dto.parking.ParkingReservationRow;
import java.util.Set;
import java.util.Map;
import java.util.Objects;
import java.util.Locale;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.ParkingSpaceUpdateRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import kr.co.alpharking.dao.parking.ParkingSpaceDao;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.ParkingUsageRow;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;
import kr.co.alpharking.websocket.parking.ParkingSpaceChangedEvent;

@Service
public class ParkingSpaceService {
    private final ParkingSpaceDao dao;
    private final ApplicationEventPublisher events;
    private final ParkingUsageDao usages;
    private final ParkingUsageService usageService;
    public ParkingSpaceService(ParkingSpaceDao dao, ApplicationEventPublisher events,
                               ParkingUsageDao usages, ParkingUsageService usageService) {
        this.dao = dao;
        this.events = events;
        this.usages = usages;
        this.usageService = usageService;
    }

    @Transactional(readOnly = true)
    // [1023_1010] 관리자 메모·차량번호를 포함할 수 있는 원본 조회. 공용 스토어 공개 현황과 구분한다.
    public List<ParkingSpaceRow> findAllAdmin() { return dao.findAllAdmin(); }

    @Transactional(readOnly = true)
    // [1023_1010] 지정일은 시작 포함/다음 날 시작 제외 경계로, upcoming은 한국 현재 시각 이후 종료 예약으로 조회한다.
    public List<ParkingReservationRow> reservations(
            Long spaceId, String rawDate, boolean upcoming) {
        if (spaceId != null && dao.findById(spaceId) == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "주차구획이 존재하지 않습니다.");
        }
        if (upcoming) {
            return dao.findReservations(spaceId, Timestamp.valueOf(
                    LocalDateTime.now(java.time.ZoneId.of("Asia/Seoul"))), null);
        }
        try {
            java.time.LocalDate date = java.time.LocalDate.parse(rawDate);
            if (date.getYear() < 1900 || date.getYear() > 9998) throw new IllegalArgumentException();
            return dao.findReservations(spaceId, Timestamp.valueOf(date.atStartOfDay()),
                    Timestamp.valueOf(date.plusDays(1).atStartOfDay()));
        } catch (IllegalArgumentException | java.time.format.DateTimeParseException exception) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "조회 날짜를 YYYY-MM-DD 형식으로 입력해 주세요.");
        }
    }

    @Transactional(readOnly = true)
    // [1023_1010] 구획 존재를 확인한 뒤 날짜·취소 제한 없는 관리자 이력을 조회한다.
    public List<ParkingReservationRow> reservationHistory(Long spaceId) {
        if (spaceId == null || dao.findById(spaceId) == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "주차구획이 존재하지 않습니다.");
        }
        return dao.findReservationHistory(spaceId);
    }

    @Transactional(readOnly = true)
    // [1023_1010] 민감 필드를 제외하고 예약을 표시 상태에 반영한 현황 조회. DB 원본은 수정하지 않는다.
    public List<ParkingSpacePublicRow> findAllPublic() { return dao.findAllPublic(); }

    private static final Set<String> ALLOWED_STATUSES = Set.of("AVAILABLE", "OCCUPIED", "RESERVED", "DISABLED");
    private static final Set<String> ALLOWED_TYPES = Set.of("NORMAL", "ELECTRIC", "DISABLED", "DISABLED_PERSON");

    @Transactional(readOnly = true)
    // [1023_1010] 조회 시점 기준값을 패널에 제공한다. 실제 저장 때에는 잠금 후 동일한 기준인지 다시 검사한다.
    public Map<String, Object> correctionDetail(Long id) {
        ParkingSpaceRow space = dao.findById(id);
        if (space == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "주차구획이 존재하지 않습니다.");
        return Map.of("space", space, "activeUsages", usages.findActiveOnSpace(id), "history", dao.findHistory(id));
    }

    @Transactional(readOnly = true)
    // [1023_1010] 검색 문자열을 정규화하고 형식을 확인한 뒤 기존 미출차 기록만 찾는다.
    public List<ParkingUsageRow> searchActive(String rawNumber) {
        String number = rawNumber == null ? "" : rawNumber.replaceAll("\\s+", "");
        if (!number.matches("[0-9가-힣]{2,20}")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "차량번호를 두 글자 이상 입력해 주세요.");
        }
        return usages.searchActive(number);
    }

    /** 화면의 저장 버튼에서 호출: 변경과 이력 기록을 하나의 트랜잭션으로 처리. */
    @Transactional
    // [1023_1010] 구획·이용 기록·사유 이력을 묶는 저장 트랜잭션이다. 중간 예외는 전체 저장을 취소한다.
    public ParkingSpaceRow updateSpace(Long id, ParkingSpaceUpdateRequest request, Long adminId) {
        if (request == null || id == null || adminId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "잘못된 요청입니다.");
        }
        String status = request.spaceStatusCode() == null ? "" : request.spaceStatusCode().trim().toUpperCase(Locale.ROOT);
        String type = request.spaceTypeCode() == null ? "" : request.spaceTypeCode().trim().toUpperCase(Locale.ROOT);
        String memo = request.memo() == null ? "" : request.memo().trim();
        String reason = request.changeReason() == null ? "" : request.changeReason().trim();
        if (!ALLOWED_STATUSES.contains(status) || !ALLOWED_TYPES.contains(type)
                || reason.isBlank() || reason.length() > 250 || memo.length() > 500) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "상태/종류/메모/변경 사유를 확인하세요.");
        }
        if (request.expectedStatus() == null || request.expectedType() == null
                || request.expectedActiveUsageIds() == null || request.usageAction() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "최신 보정 패널에서 구획을 다시 조회해 주세요.");
        }
        String action = request.usageAction();
        if (!Set.of("KEEP", "ASSIGN", "DETACH", "EXIT").contains(action)
                || ("DISABLED".equals(type) && !"DISABLED".equals(status))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "구획 종류와 보정 작업을 확인해 주세요.");
        }
        // [1023_1010] 구획을 먼저 잠그고 expected 상태·종류·메모·수정시각·이력 ID가 그대로인지 비교한다.
        ParkingSpaceRow previous = dao.lockForUpdate(id);
        if (previous == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "주차구획이 존재하지 않습니다.");
        if (!Objects.equals(request.expectedStatus(), previous.getSpaceStatusCode())
                || !Objects.equals(request.expectedType(), previous.getSpaceTypeCode())
                || !text(request.expectedMemo()).equals(text(previous.getMemo()))
                || !Objects.equals(request.expectedUpdatedAt(), previous.getUpdatedAt())
                || !Objects.equals(request.expectedHistoryId(), dao.latestHistoryId(id))) {
            conflict("조회 후 구획 정보가 변경되었습니다. 입력을 보존한 채 최신 정보를 확인하고 다시 저장해 주세요.");
        }
        // [1023_1010] 조회 당시 연결 기록 목록도 대조해 차량 연결 변경을 덮어쓰지 않게 한다.
        List<ParkingUsageRow> active = usages.lockActiveOnSpace(id);
        List<Long> actualIds = active.stream().map(ParkingUsageRow::getParkingUsageId).sorted().toList();
        if (request.expectedActiveUsageIds().stream().anyMatch(Objects::isNull)
                || !actualIds.equals(request.expectedActiveUsageIds().stream().sorted().toList())) {
            conflict("연결된 차량 기록이 변경되었습니다. 최신 정보를 다시 조회해 주세요.");
        }
        if (active.size() > 1) conflict("한 구획에 여러 미출차 기록이 있습니다. 이용 기록을 먼저 확인해 주세요.");
        String beforeUsage = active.isEmpty() ? "없음" : describe(active.getFirst());
        ParkingUsageRow affected = null;
        boolean usageChanged = false;
        // [1023_1010] 사용중 보정은 기존 미출차 기록을 선택해야 한다. 다른 구획 연결·중복 번호판·점유 충돌을 거절한다.
        if ("ASSIGN".equals(action)) {
            if (!"OCCUPIED".equals(status) || request.parkingUsageId() == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "사용중으로 연결할 기존 입차 기록을 선택해 주세요.");
            }
            // 교체는 먼저 기존 연결을 해제한 뒤 수행한다. 서로 다른 두 이용 기록을 동시에 잠그지 않는다.
            if (!active.isEmpty() && !Objects.equals(active.getFirst().getParkingUsageId(), request.parkingUsageId())) {
                conflict("다른 차량이 연결된 구획입니다. 기존 차량 기록을 먼저 정리해 주세요.");
            }
            affected = usages.lockOpenUsage(request.parkingUsageId());
            if (affected == null) conflict("선택한 기록이 이미 출차 처리되었습니다. 다시 검색해 주세요.");
            if (!Objects.equals(affected.getVehicleNumber(), request.vehicleNumber())) {
                conflict("선택한 차량 정보가 변경되었습니다. 다시 검색해 주세요.");
            }
            if (usages.countActiveByPlate(affected.getVehicleNumber()) != 1) {
                conflict("동일 차량번호의 미출차 기록이 여러 건입니다. 이용 기록을 먼저 확인해 주세요.");
            }
            if (affected.getParkingSpaceId() != null && !id.equals(affected.getParkingSpaceId())) {
                conflict("다른 구획에 연결된 차량입니다. 기존 구획에서 연결을 해제한 뒤 선택해 주세요.");
            }
            if (usages.countOtherActiveOnSpace(id, affected.getParkingUsageId()) > 0) {
                conflict("다른 차량이 연결된 구획입니다. 기존 차량 기록을 먼저 정리해 주세요.");
            }
            usageChanged = affected.getParkingSpaceId() == null;
            if (usageChanged && usages.assignSpace(affected.getParkingUsageId(), id) != 1) conflict("차량 연결 상태가 변경되었습니다.");
        // [1023_1010] DETACH는 입차 기록을 유지하고 구획만 해제한다. EXIT는 실제 출차 시각까지 검증해 출차 처리한다.
        } else if ("DETACH".equals(action) || "EXIT".equals(action)) {
            if (!"AVAILABLE".equals(status) || active.size() != 1
                    || !Objects.equals(request.parkingUsageId(), active.getFirst().getParkingUsageId())) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "사용가능 처리할 현재 연결 차량을 확인해 주세요.");
            }
            affected = active.getFirst();
            if ("EXIT".equals(action)) {
                final LocalDateTime exit;
                try { exit = LocalDateTime.parse(request.exitAt()); }
                catch (RuntimeException exception) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "실제 출차 시각을 입력해 주세요.");
                }
                if (exit.isAfter(LocalDateTime.now())) {
                    throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "미래 시각으로 출차 처리할 수 없습니다.");
                }
                // 이용 기록은 기존 출차 서비스에서 입차 시각을 포함해 다시 검증한다.
                usageService.exitAt(affected.getParkingUsageId(), Timestamp.valueOf(exit));
            } else if (usages.detachSpace(affected.getParkingUsageId(), id) != 1) {
                conflict("차량 연결 상태가 변경되었습니다.");
            }
            usageChanged = true;
        } else {
            if ("AVAILABLE".equals(status) && !active.isEmpty()) {
                conflict("차량이 연결되어 있습니다. 구획 연결 해제 또는 누락 출차 처리를 선택해 주세요.");
            }
            if ("OCCUPIED".equals(status) && active.size() != 1) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "사용중 구획에는 기존 입차 기록을 연결해 주세요.");
            }
        }
        if (!usageChanged && status.equals(previous.getSpaceStatusCode()) && type.equals(previous.getSpaceTypeCode())
                && memo.equals(text(previous.getMemo()))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "변경된 내용이 없습니다.");
        }
        // [1023_1010] 사유만 저장하지 않고 이전/이후 상태·종류·대상 기록·작업을 함께 이력 문자열에 남긴다.
        String audit = "[보정] " + previous.getSpaceStatusCode() + "→" + status
                + " / 종류 " + previous.getSpaceTypeCode() + "→" + type
                + " / " + action + " / 기존 " + beforeUsage
                + (affected == null ? "" : " / 대상 " + describe(affected))
                + ("ASSIGN".equals(action) ? "→구획 " + id : "DETACH".equals(action) ? "→구획 미연결" : "")
                + ("EXIT".equals(action) ? " / 출차 " + request.exitAt() : "") + " / 사유: " + reason;
        // [1023_1010] 실제 컬럼의 문자/바이트 제한을 확인한다. 내용을 몰래 자르거나 컬럼을 변경하지 않는다.
        if (dao.countValidTextColumns(memo, audit) != 3) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "메모 또는 보정 이력이 기존 DB 컬럼 길이를 초과합니다. 입력을 줄여 주세요.");
        }
        if (dao.updateAdminSpace(id, status, type, memo) != 1) {
            throw new IllegalStateException("구획 수정 실패");
        }
        dao.closeOpenHistory(id);
        if (dao.insertAdminHistory(id, adminId, audit) != 1) {
            throw new IllegalStateException("구획 변경 이력 저장 실패");
        }
        // [1023_1010] 트랜잭션 내에서 이벤트를 발행하되 실제 전송 리스너는 커밋 완료 후 실행된다.
        events.publishEvent(new ParkingSpaceChangedEvent());
        return dao.findById(id);
    }

    // [1023_1010] null과 빈 메모를 비교·감사 문자열에서 일관되게 취급한다.
    private static String text(String value) { return value == null ? "" : value; }
    // [1023_1010] 감사 이력에 이용 기록 ID·차량번호·구획을 식별 가능한 문자열로 기록한다.
    private static String describe(ParkingUsageRow usage) {
        return "#" + usage.getParkingUsageId() + " " + usage.getVehicleNumber()
                + "(구획 " + usage.getParkingSpaceId() + ")";
    }
    // [1023_1010] 동시 변경·연결 충돌을 HTTP 409로 전달한다.
    private static void conflict(String message) {
        throw new ResponseStatusException(HttpStatus.CONFLICT, message);
    }
}
