/** 파일 안내
 * 용도: 관리자 대시보드의 일별 통계와 최근 입출차 조회 API를 제공한다.
 * 직접 사용처: 프론트 dashboardApi의 /api/dashboard 요청 → DashboardService.
 * 두 조회 모두 JWT의 관리자 principal·관리자 PK·ADMIN 권한을 확인한다.
 * 통계 생성이나 입출차 변경은 하지 않는다. 구획·차량 신청은 각 기존 API에서 따로 조회한다.
 */
package kr.co.alpharking.controller.dashboard;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.dashboard.DailyParkingSummaryRow;
import kr.co.alpharking.dto.dashboard.DashboardParkingEventRow;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.dashboard.DashboardService;

/** /admin/dashboard의 일별 통계 조회. 관리자 인증·권한을 모두 확인한다. */
@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {
    private final DashboardService service;

    public DashboardController(DashboardService service) { this.service = service; }

    /** week/month 선택을 서비스에 전달한다. 기간 검증과 한국 날짜 범위 계산은 서비스가 담당한다. */
    @GetMapping("/daily-parking-summary")
    public List<DailyParkingSummaryRow> dailyParkingSummary(
            @RequestParam(name = "period", defaultValue = "week") String period,
            Authentication authentication) {
        requireAdmin(authentication);
        return service.recentDailySummary(period);
    }

    /** 입차와 출차를 별개 이벤트로 합쳐 최신 5건만 조회한다. */
    @GetMapping("/recent-parking-events")
    public List<DashboardParkingEventRow> recentParkingEvents(Authentication authentication) {
        requireAdmin(authentication);
        return service.recentParkingEvents();
    }

    /** 요청자가 보낸 관리자 ID 대신 서버에서 인증한 계정과 권한을 확인한다. */
    private void requireAdmin(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        if (!(authentication.getPrincipal() instanceof Admin admin) || admin.getAdmin_id() == null
                || authentication.getAuthorities().stream().noneMatch(authority -> "ADMIN".equals(authority.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
    }
}
