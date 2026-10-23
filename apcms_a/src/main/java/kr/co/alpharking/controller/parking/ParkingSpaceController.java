/** [1023_1010] 파일 안내
 * 용도: 관리자 구획 조회·보정·예약 읽기 API의 HTTP 진입점.
 * 사용처·연결: parkingSpaceApi → /api/parking/spaces → ParkingSpaceService.
 * 관리자 상세·보정은 ADMIN을 검사한다. /public은 민감 필드를 제외하며 접근 정책은 SecurityConfig도 적용된다.
 */
package kr.co.alpharking.controller.parking;

import java.util.List;
import kr.co.alpharking.dto.parking.ParkingReservationRow;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpaceUpdateRequest;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;
import kr.co.alpharking.dto.parking.ParkingUsageRow;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.parking.ParkingSpaceService;

/** 주차구획 조회 및 JWT로 인증된 관리자의 구획 변경. */
@RestController
@RequestMapping("/api/parking/spaces")
public class ParkingSpaceController {
    private final ParkingSpaceService service;
    public ParkingSpaceController(ParkingSpaceService service) { this.service = service; }

    // [1023_1010] 로그인·principal·관리자 PK·ADMIN authority를 함께 확인한다. 요청 본문의 관리자 ID를 신뢰하지 않는다.
    private Admin requireAdmin(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        if (!(authentication.getPrincipal() instanceof Admin admin) || admin.getAdmin_id() == null
                || authentication.getAuthorities().stream().noneMatch(authority -> "ADMIN".equals(authority.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
        return admin;
    }

    /** 관리자 강제 변경: JWT로 인증된 관리자의 PK로 이력을 저장한다. */
    // [1023_1010] 상태 변경 요청. 서비스에서 상태·이용 기록·이력 저장을 한 트랜잭션으로 처리한다.
    @PatchMapping("/{parkingSpaceId}")
    public ParkingSpaceRow updateSpace(@PathVariable("parkingSpaceId") Long parkingSpaceId,
                                       @RequestBody ParkingSpaceUpdateRequest request,
                                       Authentication authentication) {
        Admin admin = requireAdmin(authentication);
        return service.updateSpace(parkingSpaceId, request, admin.getAdmin_id());
    }

    // [1023_1010] 보정용 구획 원본·미출차 기록·최근 이력을 묶어서 반환한다.
    @GetMapping("/{parkingSpaceId}/correction")
    public Map<String, Object> correction(@PathVariable("parkingSpaceId") Long parkingSpaceId, Authentication authentication) {
        requireAdmin(authentication);
        return service.correctionDetail(parkingSpaceId);
    }

    // [1023_1010] 차량번호로 보정에 연결할 기존 미출차 후보를 조회한다.
    @GetMapping("/usage-candidates")
    public List<ParkingUsageRow> usageCandidates(@RequestParam("vehicleNumber") String vehicleNumber, Authentication authentication) {
        requireAdmin(authentication);
        return service.searchActive(vehicleNumber);
    }

    // [1023_1010] 전체 구획의 지정일 확정 예약을 조회한다. 관리자 오늘 예약 카드에서 사용한다.
    @GetMapping("/reservations")
    public List<ParkingReservationRow> reservations(
            @RequestParam("date") String date, Authentication authentication) {
        requireAdmin(authentication);
        return service.reservations(null, date, false);
    }

    // [1023_1010] 특정 구획의 지정일 또는 진행 중·향후 확정 예약 조회 경로다.
    @GetMapping("/{parkingSpaceId}/reservations")
    public List<ParkingReservationRow> spaceReservations(
            @PathVariable("parkingSpaceId") Long parkingSpaceId,
            @RequestParam(value = "date", defaultValue = "") String date,
            @RequestParam(value = "upcoming", defaultValue = "false") boolean upcoming,
            Authentication authentication) {
        requireAdmin(authentication);
        return service.reservations(parkingSpaceId, date, upcoming);
    }

    // [1023_1010] 달력 표시용 전체 구획의 진행 중·향후 확정 예약 조회. 현재 점유 상태와 별개다.
    @GetMapping("/reservations/upcoming")
    public List<ParkingReservationRow> upcomingReservations(Authentication authentication) {
        requireAdmin(authentication);
        return service.reservations(null, "", true);
    }

    // [1023_1010] 예약 내역 탭의 전체 날짜 이력 조회. 취소·지난 예약을 포함한다.
    @GetMapping("/{parkingSpaceId}/reservation-history")
    public List<ParkingReservationRow> reservationHistory(
            @PathVariable("parkingSpaceId") Long parkingSpaceId, Authentication authentication) {
        requireAdmin(authentication);
        return service.reservationHistory(parkingSpaceId);
    }

    /** Spring 기본 오류 본문 설정과 무관하게 보정 실패 사유를 패널에 전달한다. */
    // [1023_1010] 상태 코드는 유지하고 사용자에게 보여 줄 실패 사유를 message 필드로 통일한다.
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, String>> requestFailure(ResponseStatusException exception) {
        return ResponseEntity.status(exception.getStatusCode())
                .body(Map.of("message", exception.getReason() == null ? "요청을 처리할 수 없습니다." : exception.getReason()));
    }

    // [1023_1010] 동시 작업의 잠금 충돌을 409로 안내한다. 무조건 재저장하지 않고 재조회를 유도한다.
    @ExceptionHandler(PessimisticLockingFailureException.class)
    public ResponseEntity<Map<String, String>> locked() {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Map.of("message", "다른 작업에서 기록을 변경 중입니다. 최신 정보를 조회한 뒤 다시 시도해 주세요."));
    }

    // [1023_1010] DB 제약 위반을 409로 안내한다. 저장 트랜잭션이 실패하면 구획·이용 기록·이력이 함께 롤백된다.
    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<Map<String, String>> integrityFailure() {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Map.of("message", "기존 DB 제약조건으로 저장하지 못했습니다. 모든 변경은 취소되었습니다. 서버 로그를 확인해 주세요."));
    }

    /** 로그인 사용자용 현황. 메모/차량번호를 노출하지 않음. */
    @GetMapping("/public")
    public List<ParkingSpacePublicRow> publicSpaces() { return service.findAllPublic(); }

    /** 관리자 화면. JWT 인증 및 관리자 권한이 필요하다. */
    @GetMapping
    public List<ParkingSpaceRow> adminSpaces(Authentication authentication) {
        requireAdmin(authentication);
        return service.findAllAdmin();
    }
}
