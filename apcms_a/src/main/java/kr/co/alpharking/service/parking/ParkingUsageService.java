/** 파일 안내
 * 용도: 등록·방문 차량 입출차와 점유 구획 연결 처리.
 * 사용처·연결: ParkingUsageController, AiVehicleEventService, ParkingSpaceService → ParkingUsageDao.
 * AI 배정 충돌은 결과로 반환한다. 관리자 배정의 예외 방식과 합치면 PENDING·롤백 처리에 영향을 줄 수 있다.
 */
package kr.co.alpharking.service.parking;

import java.sql.Timestamp;
import java.util.List;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.ParkingUsageRow;

@Service
public class ParkingUsageService {
    private static final Pattern PLATE = Pattern.compile("^[0-9]{2,3}[가-힣][0-9]{4}$");
    private final ParkingUsageDao dao;
    public ParkingUsageService(ParkingUsageDao dao) { this.dao = dao; }

    /** AI/관리자 공통 입차. 미등록 차량은 차량번호만 기록하며 출입 허가를 판정하지 않는다. */
    @Transactional
    // 관리자 수동 입차는 서버 현재 시각을 사용한다. AI는 감지 시각을 받는 enterAt을 사용한다.
    public ParkingUsageRow enter(String rawNumber) {
        return enterAt(rawNumber, new Timestamp(System.currentTimeMillis()));
    }

    @Transactional
    // 차량번호 정규화 후 열린 이용 기록 중복을 확인하고 등록/방문 유형으로 입차를 저장한다.
    public ParkingUsageRow enterAt(String rawNumber, Timestamp eventTime) {
        String number = normalize(rawNumber);
        if (eventTime == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "입차 시각이 필요합니다.");
        // REGISTERED 차량만 ID를 연결한다. 해당 조건에 맞지 않으면 번호판 기반 방문 이용으로 기록한다.
        Long registeredId = dao.lockRegisteredVehicle(number);
        if (dao.findOpenUsageByPlate(number) != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 입차 처리된 차량입니다.");
        }
        if (dao.insertEntry(registeredId, number, registeredId == null ? "VISITOR" : "NORMAL", eventTime) != 1) {
            throw new IllegalStateException("입차 저장에 실패했습니다.");
        }
        Long usageId = dao.insertedUsageId();
        ParkingUsageRow saved = dao.findById(usageId);
        if (saved == null) throw new IllegalStateException("입차 기록 재조회에 실패했습니다.");
        return saved;
    }

    @Transactional
    // 수동 출차의 현재 시각을 공통 출차 처리에 전달한다.
    public ParkingUsageRow exit(Long usageId) {
        return exitAt(usageId, new Timestamp(System.currentTimeMillis()));
    }

    @Transactional
    // 미출차 기록을 잠그고 입차 이전 시각인지 검사한 뒤 한 번만 출차 갱신한다.
    public ParkingUsageRow exitAt(Long usageId, Timestamp eventTime) {
        if (eventTime == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "출차 시각이 필요합니다.");
        ParkingUsageRow current = dao.lockOpenUsage(usageId);
        if (current == null) throw new ResponseStatusException(HttpStatus.CONFLICT, "미출차 이용 기록이 존재하지 않습니다.");
        // 감지 시각이 입차보다 빠르면 잘못된 출차 이벤트로 처리하지 않는다.
        ParkingUsageRow full = dao.findById(usageId);
        if (full != null && full.getEntryAt() != null &&
            eventTime.toLocalDateTime().isBefore(java.time.LocalDateTime.parse(full.getEntryAt()))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "입차 이전 출차 이벤트입니다.");
        }
        if (dao.exitUsage(usageId, eventTime) != 1) throw new IllegalStateException("출차 저장에 실패했습니다.");
        return dao.findById(usageId);
    }

    @Transactional
    // 관리자 수동 배정: 예상 가능한 충돌도 409 예외로 반환하는 경로다.
    public ParkingUsageRow assign(Long usageId, Long spaceId) {
        AssignmentResult result = assignInternal(usageId, spaceId);
        if (result.conflictReason() != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, result.conflictReason());
        }
        return result.usage();
    }

    /** AI의 예상 가능한 배정 충돌은 예외 대신 보류 결과로 반환한다. */
    @Transactional
    // AI 배정 충돌은 정상 결과로 돌려 상위 서비스가 PENDING으로 처리하게 한다. 롤백 전용 상태 전파를 피한다.
    public AssignmentResult assignForAi(Long usageId, Long spaceId) {
        return assignInternal(usageId, spaceId);
    }

    // conflictReason이 null이면 성공, 값이 있으면 배정 보류다. 보류 시 usage는 null일 수 있다.
    public record AssignmentResult(ParkingUsageRow usage, String conflictReason) {}

    // 예약 검증이 추가된 AI 배정 결과 계약이다. 실제 잠금·연결 처리는 아래 메서드가 수행한다.
    public record ReservedAssignmentResult(ParkingUsageRow usage, String conflictReason, boolean unchanged, String parkingDecision) {
        public ReservedAssignmentResult(ParkingUsageRow usage, String conflictReason, boolean unchanged) {
            this(usage, conflictReason, unchanged, conflictReason == null ? "MATCHED" : "UNDETERMINED");
        }
    }

    /** AI 연결만 예약을 검증한다. 관리자 수동 연결의 기존 정책은 유지한다. */
    @Transactional
    public ReservedAssignmentResult assignReservedForAi(Long usageId, Long spaceId, String rawNumber, Timestamp eventTime) {
        String number = normalize(rawNumber);
        if (usageId == null || spaceId == null || eventTime == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "이용·구획·감지 시각이 필요합니다.");
        }
        // 관리자 보정과 같은 순서로 구획, 이용, 예약을 잠근다.
        if (!"OCCUPIED".equals(dao.lockSpaceStatus(spaceId))) return held("점유로 확인된 구획이 아닙니다.");
        ParkingUsageRow current = dao.lockOpenUsage(usageId);
        if (current == null || !number.equals(current.getVehicleNumber()) || dao.countActiveByPlate(number) != 1) {
            return held("활성 입차 기록을 유일하게 확인할 수 없습니다.");
        }
        if (current.getEntryAt() == null || eventTime.toLocalDateTime().isBefore(java.time.LocalDateTime.parse(current.getEntryAt()))) {
            return held("입차 이전의 매칭 이벤트입니다.");
        }
        Timestamp correctedAt = dao.latestAdminChangedAt(spaceId);
        if (correctedAt != null && !eventTime.after(correctedAt)) return held("관리자 보정 이전의 매칭 이벤트입니다.");
        if (current.getParkingSpaceId() != null && !spaceId.equals(current.getParkingSpaceId())) {
            return held("이미 다른 구획에 연결된 차량입니다.");
        }
        if (dao.countOtherActiveOnSpace(spaceId, usageId) > 0) return held("이미 다른 차량이 연결된 구획입니다.");
        var reservations = dao.lockReservationCandidates(number, spaceId, eventTime);
        if (reservations == null) return held("예약 조회 결과를 확인할 수 없습니다.");
        // 대상 구획의 다른 차량 예약과 이 차량의 예약을 구분합니다.
        var ownReservations = reservations.stream().filter(r -> r != null && number.equals(r.getVehicleNumber())).toList();
        if (reservations.stream().anyMatch(r -> r == null || r.getParkingReservationId() == null
                || r.getParkingSpaceId() == null || !"CONFIRMED".equals(r.getStatusCode()))) {
            return held("예약 상태를 확인할 수 없습니다.");
        }
        if (ownReservations.isEmpty()) return new ReservedAssignmentResult(null, "현재 유효한 차량 예약이 없습니다.", false, "NO_VALID_RESERVATION");
        if (ownReservations.size() != 1) return held("차량의 유효 예약이 중복되어 판정할 수 없습니다.");
        if (!spaceId.equals(ownReservations.getFirst().getParkingSpaceId())) {
            return new ReservedAssignmentResult(null, "예약한 구획과 실제 정차 구획이 다릅니다.", false, "WRONG_SPACE");
        }
        if (reservations.size() != 1) return held("일치하는 유효 예약을 유일하게 확인할 수 없습니다.");
        var reservation = reservations.getFirst();
        if (!spaceId.equals(reservation.getParkingSpaceId()) || !number.equals(reservation.getVehicleNumber())
                || !"CONFIRMED".equals(reservation.getStatusCode()) || reservation.getParkingReservationId() == null) {
            return held("예약 차량 또는 구획이 일치하지 않습니다.");
        }
        Long reservationId = reservation.getParkingReservationId();
        if (current.getParkingReservationId() != null && !reservationId.equals(current.getParkingReservationId())) {
            return held("이미 다른 예약에 연결된 이용 기록입니다.");
        }
        boolean unchanged = spaceId.equals(current.getParkingSpaceId()) && reservationId.equals(current.getParkingReservationId());
        int updated = dao.assignReservedSpace(usageId, spaceId, reservationId, number, eventTime);
        if (updated == 0) {
            return held("예약 또는 이용 상태가 변경되어 연결하지 않았습니다.");
        }
        if (updated != 1) throw new IllegalStateException("구획·예약 연결 반영 건수가 올바르지 않습니다.");
        ParkingUsageRow saved = dao.findById(usageId);
        if (saved == null || !spaceId.equals(saved.getParkingSpaceId()) || !reservationId.equals(saved.getParkingReservationId())) {
            throw new IllegalStateException("구획·예약 연결 결과 재조회 실패");
        }
        return new ReservedAssignmentResult(saved, null, unchanged);
    }

    public record ReleaseResult(ParkingUsageRow usage, String conflictReason, Long linkVersion) {}

    /** 서버의 AVAILABLE 상태와 연결 버전을 함께 확인한다. */
    @Transactional
    public ReleaseResult releaseForAi(Long usageId, Long spaceId, String rawNumber,
                                      Long expectedVersion, Timestamp eventTime) {
        String number = normalize(rawNumber);
        if (usageId == null || usageId < 1 || spaceId == null || expectedVersion == null
                || expectedVersion < 0 || expectedVersion == Long.MAX_VALUE || eventTime == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "해제 이용·구획·버전·시각을 확인하세요.");
        }
        // 점유만 해제됐다고 이용 연결을 지우지 않는다. 이용·차량·세대가 모두 일치해야 한다.
        if (!"AVAILABLE".equals(dao.lockSpaceStatus(spaceId))) return new ReleaseResult(null, "빈 구획으로 확인되지 않았습니다.", null);
        ParkingUsageRow current = dao.lockOpenUsage(usageId);
        if (current == null || !number.equals(current.getVehicleNumber()) || dao.countActiveByPlate(number) != 1
                || !spaceId.equals(current.getParkingSpaceId())) {
            return new ReleaseResult(null, "현재 이용·차량·기존 구획이 일치하지 않습니다.", null);
        }
        if (current.getEntryAt() == null || eventTime.toLocalDateTime().isBefore(java.time.LocalDateTime.parse(current.getEntryAt()))) {
            return new ReleaseResult(null, "입차 이전의 해제 이벤트입니다.", null);
        }
        Timestamp corrected = dao.latestAdminChangedAt(spaceId);
        if (corrected != null && !eventTime.after(corrected)) return new ReleaseResult(null, "관리자 보정 이전의 해제입니다.", null);
        Long version = dao.lockLinkVersion(usageId);
        if (!expectedVersion.equals(version)) return new ReleaseResult(null, "연결 버전이 변경되었습니다.", null);
        int updated = dao.releaseAiSpace(usageId, spaceId, number, expectedVersion);
        if (updated == 0) return new ReleaseResult(null, "연결 상태가 변경되었습니다.", null);
        if (updated != 1) throw new IllegalStateException("구획 해제 반영 건수 오류");
        ParkingUsageRow saved = dao.findById(usageId);
        Long nextVersion = dao.lockLinkVersion(usageId);
        if (saved == null || !usageId.equals(saved.getParkingUsageId()) || !number.equals(saved.getVehicleNumber())
                || saved.getExitAt() != null || saved.getParkingSpaceId() != null || saved.getParkingReservationId() != null
                || nextVersion == null || nextVersion != expectedVersion + 1) {
            throw new IllegalStateException("구획 해제·버전 갱신 결과 재조회 실패");
        }
        saved.setLinkVersion(nextVersion);
        return new ReleaseResult(saved, null, nextVersion);
    }

    private static ReservedAssignmentResult held(String reason) {
        return new ReservedAssignmentResult(null, reason, false);
    }

    // 구획을 먼저 잠그고 점유·활성 이용·다른 구획 연결·중복 점유를 확인한 뒤 연결한다.
    private AssignmentResult assignInternal(Long usageId, Long spaceId) {
        if (usageId == null || spaceId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "이용 기록과 주차구획 ID가 필요합니다.");
        }
        String status = dao.lockSpaceStatus(spaceId);
        if (status == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "주차구획을 찾을 수 없습니다.");
        if (!"OCCUPIED".equals(status)) {
            return new AssignmentResult(null, "AI에서 점유로 확인된 구획만 연결할 수 있습니다.");
        }
        ParkingUsageRow current = dao.lockOpenUsage(usageId);
        if (current == null) return new AssignmentResult(null, "미출차 이용 기록이 없습니다.");
        if (current.getParkingSpaceId() != null && !spaceId.equals(current.getParkingSpaceId())) {
            return new AssignmentResult(null, "이미 다른 구획에 연결된 차량입니다.");
        }
        if (dao.countOtherActiveOnSpace(spaceId, usageId) > 0) {
            return new AssignmentResult(null, "이미 다른 차량이 연결된 구획입니다.");
        }
        if (dao.assignSpace(usageId, spaceId) != 1) throw new IllegalStateException("구획 연결 실패");
        ParkingUsageRow saved = dao.findById(usageId);
        if (saved == null) throw new IllegalStateException("구획 연결 결과 재조회 실패");
        return new AssignmentResult(saved, null);
    }

    // 서버에서 공백을 제거하고 국내 번호판 형식을 확인한다. 프론트 검사만 신뢰하지 않는다.
    private static String normalize(String raw) {
        String value = raw == null ? "" : raw.replaceAll("\\s+", "").trim();
        if (!PLATE.matcher(value).matches())
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "차량번호 형식을 확인하세요.");
        return value;
    }

    @Transactional(readOnly = true)
    // 현재 미출차 전체 목록 조회. 변경 SQL은 실행하지 않는다.
    public List<ParkingUsageRow> active() { return dao.findActive(); }
    @Transactional(readOnly = true)
    // 관리자 최근 입출차 목록 조회. XML의 최신 200건 제한이 적용된다.
    public List<ParkingUsageRow> recent() { return dao.findRecent(); }
}
