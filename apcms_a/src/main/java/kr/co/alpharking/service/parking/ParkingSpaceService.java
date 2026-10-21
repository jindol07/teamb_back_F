package kr.co.alpharking.service.parking;

import java.util.List;
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
    public List<ParkingSpaceRow> findAllAdmin() { return dao.findAllAdmin(); }

    @Transactional(readOnly = true)
    public List<ParkingSpacePublicRow> findAllPublic() { return dao.findAllPublic(); }

    private static final Set<String> ALLOWED_STATUSES = Set.of("AVAILABLE", "OCCUPIED", "RESERVED", "DISABLED");
    private static final Set<String> ALLOWED_TYPES = Set.of("NORMAL", "ELECTRIC", "DISABLED", "DISABLED_PERSON");

    @Transactional(readOnly = true)
    public Map<String, Object> correctionDetail(Long id) {
        ParkingSpaceRow space = dao.findById(id);
        if (space == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "주차구획이 존재하지 않습니다.");
        return Map.of("space", space, "activeUsages", usages.findActiveOnSpace(id), "history", dao.findHistory(id));
    }

    @Transactional(readOnly = true)
    public List<ParkingUsageRow> searchActive(String rawNumber) {
        String number = rawNumber == null ? "" : rawNumber.replaceAll("\\s+", "");
        if (!number.matches("[0-9가-힣]{2,20}")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "차량번호를 두 글자 이상 입력해 주세요.");
        }
        return usages.searchActive(number);
    }

    /** 화면의 저장 버튼에서 호출: 변경과 이력 기록을 하나의 트랜잭션으로 처리. */
    @Transactional
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
        ParkingSpaceRow previous = dao.lockForUpdate(id);
        if (previous == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "주차구획이 존재하지 않습니다.");
        if (!Objects.equals(request.expectedStatus(), previous.getSpaceStatusCode())
                || !Objects.equals(request.expectedType(), previous.getSpaceTypeCode())
                || !text(request.expectedMemo()).equals(text(previous.getMemo()))
                || !Objects.equals(request.expectedUpdatedAt(), previous.getUpdatedAt())
                || !Objects.equals(request.expectedHistoryId(), dao.latestHistoryId(id))) {
            conflict("조회 후 구획 정보가 변경되었습니다. 입력을 보존한 채 최신 정보를 확인하고 다시 저장해 주세요.");
        }
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
        String audit = "[보정] " + previous.getSpaceStatusCode() + "→" + status
                + " / 종류 " + previous.getSpaceTypeCode() + "→" + type
                + " / " + action + " / 기존 " + beforeUsage
                + (affected == null ? "" : " / 대상 " + describe(affected))
                + ("ASSIGN".equals(action) ? "→구획 " + id : "DETACH".equals(action) ? "→구획 미연결" : "")
                + ("EXIT".equals(action) ? " / 출차 " + request.exitAt() : "") + " / 사유: " + reason;
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
        events.publishEvent(new ParkingSpaceChangedEvent());
        return dao.findById(id);
    }

    private static String text(String value) { return value == null ? "" : value; }
    private static String describe(ParkingUsageRow usage) {
        return "#" + usage.getParkingUsageId() + " " + usage.getVehicleNumber()
                + "(구획 " + usage.getParkingSpaceId() + ")";
    }
    private static void conflict(String message) {
        throw new ResponseStatusException(HttpStatus.CONFLICT, message);
    }
}
