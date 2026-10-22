package kr.co.alpharking.controller.parking;

import java.util.List;
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
    @PatchMapping("/{parkingSpaceId}")
    public ParkingSpaceRow updateSpace(@PathVariable("parkingSpaceId") Long parkingSpaceId,
                                       @RequestBody ParkingSpaceUpdateRequest request,
                                       Authentication authentication) {
        Admin admin = requireAdmin(authentication);
        return service.updateSpace(parkingSpaceId, request, admin.getAdmin_id());
    }

    @GetMapping("/{parkingSpaceId}/correction")
    public Map<String, Object> correction(@PathVariable("parkingSpaceId") Long parkingSpaceId, Authentication authentication) {
        requireAdmin(authentication);
        return service.correctionDetail(parkingSpaceId);
    }

    @GetMapping("/usage-candidates")
    public List<ParkingUsageRow> usageCandidates(@RequestParam("vehicleNumber") String vehicleNumber, Authentication authentication) {
        requireAdmin(authentication);
        return service.searchActive(vehicleNumber);
    }

    @GetMapping("/reservations")
    public List<kr.co.alpharking.dto.parking.ParkingReservationRow> reservations(
            @RequestParam("date") String date, Authentication authentication) {
        requireAdmin(authentication);
        return service.reservations(null, date, false);
    }

    @GetMapping("/{parkingSpaceId}/reservations")
    public List<kr.co.alpharking.dto.parking.ParkingReservationRow> spaceReservations(
            @PathVariable("parkingSpaceId") Long parkingSpaceId,
            @RequestParam(value = "date", defaultValue = "") String date,
            @RequestParam(value = "upcoming", defaultValue = "false") boolean upcoming,
            Authentication authentication) {
        requireAdmin(authentication);
        return service.reservations(parkingSpaceId, date, upcoming);
    }

    @GetMapping("/reservations/upcoming")
    public List<kr.co.alpharking.dto.parking.ParkingReservationRow> upcomingReservations(Authentication authentication) {
        requireAdmin(authentication);
        return service.reservations(null, "", true);
    }

    @GetMapping("/{parkingSpaceId}/reservation-history")
    public List<kr.co.alpharking.dto.parking.ParkingReservationRow> reservationHistory(
            @PathVariable("parkingSpaceId") Long parkingSpaceId, Authentication authentication) {
        requireAdmin(authentication);
        return service.reservationHistory(parkingSpaceId);
    }

    /** Spring 기본 오류 본문 설정과 무관하게 보정 실패 사유를 패널에 전달한다. */
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, String>> requestFailure(ResponseStatusException exception) {
        return ResponseEntity.status(exception.getStatusCode())
                .body(Map.of("message", exception.getReason() == null ? "요청을 처리할 수 없습니다." : exception.getReason()));
    }

    @ExceptionHandler(PessimisticLockingFailureException.class)
    public ResponseEntity<Map<String, String>> locked() {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Map.of("message", "다른 작업에서 기록을 변경 중입니다. 최신 정보를 조회한 뒤 다시 시도해 주세요."));
    }

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
