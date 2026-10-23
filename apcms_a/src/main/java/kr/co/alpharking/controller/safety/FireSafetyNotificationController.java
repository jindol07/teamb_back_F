package kr.co.alpharking.controller.safety;

import java.util.List;
import java.util.Map;
import kr.co.alpharking.dao.safety.FireSafetyNotificationDao;
import kr.co.alpharking.security.Admin;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/** 기존 사무실 알림 API를 건드리지 않고, 현재 로그인한 관리자의 화재·연기 알림만 조회합니다. */
@RestController
@RequestMapping("/api/admin/safety-notifications")
public class FireSafetyNotificationController {
    private final FireSafetyNotificationDao dao;

    public FireSafetyNotificationController(FireSafetyNotificationDao dao) {
        this.dao = dao;
    }

    /** limit의 이름을 명시해 Java 컴파일러의 -parameters 설정에 의존하지 않습니다. */
    @GetMapping
    public List<Map<String, Object>> recent(@RequestParam(name = "limit", defaultValue = "30") int limit) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()
                || !(authentication.getPrincipal() instanceof Admin admin)
                || admin.getAdmin_id() == null
                || authentication.getAuthorities().stream()
                    .noneMatch(authority -> "ADMIN".equals(authority.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 인증이 필요합니다.");
        }
        if (limit < 1 || limit > 100) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "limit은 1~100이어야 합니다.");
        }
        // ADMIN_ID를 HTTP 파라미터로 받지 않고 인증된 관리자 본인 것으로 고정합니다.
        return dao.recentByAdmin(admin.getAdmin_id(), limit);
    }
}
