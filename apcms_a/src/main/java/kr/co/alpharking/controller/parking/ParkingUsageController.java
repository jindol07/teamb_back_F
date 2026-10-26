/** [1023_1010] 파일 안내
 * 용도: 관리자 입출차 조회·수동 입차·출차·구획 연결 API.
 * 사용처·연결: parkingUsageApi → /api/parking/usages → ParkingUsageService.
 * ParkingEntryRequest·ParkingAssignRequest는 요청 본문에 실제 사용된다. 변경 요청은 ADMIN 인증 후 처리한다.
 */
package kr.co.alpharking.controller.parking;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.*;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.parking.ParkingUsageService;
import kr.co.alpharking.service.parking.AiParkingDecisionService;

@RestController
@RequestMapping("/api/parking/usages")
public class ParkingUsageController {
    private final ParkingUsageService service;
    private final AiParkingDecisionService decisions;
    public ParkingUsageController(ParkingUsageService service, AiParkingDecisionService decisions) {
        this.service = service; this.decisions = decisions;
    }

    // 1. 판정 시점의 관리자 전용 이력입니다. 현재 점유 상태를 대체하지 않습니다.
    @GetMapping("/ai-decisions")
    public List<AiParkingDecisionRow> aiDecisions(Authentication authentication) {
        requireAdmin(authentication);
        return decisions.recent();
    }

    // [1023_1010] 모든 입출차 조회·수동 변경 경로에서 실제 관리자 인증을 확인한다.
    private void requireAdmin(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        if (!(authentication.getPrincipal() instanceof Admin admin) || admin.getAdmin_id() == null
                || authentication.getAuthorities().stream().noneMatch(authority -> "ADMIN".equals(authority.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
    }

    // [1023_1010] 미출차 전체 목록. 최근 목록의 200건 제한과 분리하여 현재 입차 수를 집계한다.
    @GetMapping("/active")
    public List<ParkingUsageRow> active(Authentication authentication) {
        requireAdmin(authentication);
        return service.active();
    }

    // [1023_1010] 관리자 목록용 최근 입출차 기록 조회.
    @GetMapping
    public List<ParkingUsageRow> recent(Authentication authentication) {
        requireAdmin(authentication);
        return service.recent();
    }

    // [1023_1010] 차량번호를 받아 서버가 등록 여부를 판정한 뒤 입차 처리한다.
    @PostMapping("/entry")
    public ParkingUsageRow entry(@RequestBody ParkingEntryRequest request, Authentication authentication) {
        requireAdmin(authentication);
        if (request == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 본문이 필요합니다.");
        return service.enter(request.vehicleNumber());
    }

    // [1023_1010] URL의 id는 이용 기록 PK다. 구획 PK와 혼동하지 않는다.
    @PatchMapping("/{id}/exit")
    public ParkingUsageRow exit(@PathVariable Long id, Authentication authentication) {
        requireAdmin(authentication);
        return service.exit(id);
    }

    // [1023_1010] URL은 이용 기록 PK, 요청 본문 parkingSpaceId는 연결할 구획 PK다.
    @PatchMapping("/{id}/space")
    public ParkingUsageRow assign(@PathVariable Long id, @RequestBody ParkingAssignRequest request, Authentication authentication) {
        requireAdmin(authentication);
        if (request == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 본문이 필요합니다.");
        return service.assign(id, request.parkingSpaceId());
    }
}
