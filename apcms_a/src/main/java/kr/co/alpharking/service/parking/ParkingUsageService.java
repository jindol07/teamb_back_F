/** [1023_1010] 파일 안내
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
    // [1023_1010] 관리자 수동 입차는 서버 현재 시각을 사용한다. AI는 감지 시각을 받는 enterAt을 사용한다.
    public ParkingUsageRow enter(String rawNumber) {
        return enterAt(rawNumber, new Timestamp(System.currentTimeMillis()));
    }

    @Transactional
    // [1023_1010] 차량번호 정규화 후 열린 이용 기록 중복을 확인하고 등록/방문 유형으로 입차를 저장한다.
    public ParkingUsageRow enterAt(String rawNumber, Timestamp eventTime) {
        String number = normalize(rawNumber);
        if (eventTime == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "입차 시각이 필요합니다.");
        // 승인된 등록 차량만 ID를 연결하며, 승인되지 않은 차량은 방문 차량처럼 번호판만 저장.
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
    // [1023_1010] 수동 출차의 현재 시각을 공통 출차 처리에 전달한다.
    public ParkingUsageRow exit(Long usageId) {
        return exitAt(usageId, new Timestamp(System.currentTimeMillis()));
    }

    @Transactional
    // [1023_1010] 미출차 기록을 잠그고 입차 이전 시각인지 검사한 뒤 한 번만 출차 갱신한다.
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
    // [1023_1010] 관리자 수동 배정: 예상 가능한 충돌도 409 예외로 반환하는 경로다.
    public ParkingUsageRow assign(Long usageId, Long spaceId) {
        AssignmentResult result = assignInternal(usageId, spaceId);
        if (result.conflictReason() != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, result.conflictReason());
        }
        return result.usage();
    }

    /** AI의 예상 가능한 배정 충돌은 예외 대신 보류 결과로 반환한다. */
    @Transactional
    // [1023_1010] AI 배정 충돌은 정상 결과로 돌려 상위 서비스가 PENDING으로 처리하게 한다. 롤백 전용 상태 전파를 피한다.
    public AssignmentResult assignForAi(Long usageId, Long spaceId) {
        return assignInternal(usageId, spaceId);
    }

    // [1023_1010] conflictReason이 null이면 성공, 값이 있으면 배정 보류다. 보류 시 usage는 null일 수 있다.
    public record AssignmentResult(ParkingUsageRow usage, String conflictReason) {}

    // [1023_1010] 구획 잠금 → 점유 확인 → 이용 기록 잠금 → 기존 연결·중복 점유 확인 → 연결 갱신 순서다.
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

    // [1023_1010] 서버에서 공백을 제거하고 국내 번호판 형식을 확인한다. 프론트 검사만 신뢰하지 않는다.
    private static String normalize(String raw) {
        String value = raw == null ? "" : raw.replaceAll("\\s+", "").trim();
        if (!PLATE.matcher(value).matches())
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "차량번호 형식을 확인하세요.");
        return value;
    }

    @Transactional(readOnly = true)
    // [1023_1010] 현재 미출차 전체 목록 조회. 변경 SQL은 실행하지 않는다.
    public List<ParkingUsageRow> active() { return dao.findActive(); }
    @Transactional(readOnly = true)
    // [1023_1010] 관리자 최근 입출차 목록 조회. XML의 최신 200건 제한이 적용된다.
    public List<ParkingUsageRow> recent() { return dao.findRecent(); }
}
