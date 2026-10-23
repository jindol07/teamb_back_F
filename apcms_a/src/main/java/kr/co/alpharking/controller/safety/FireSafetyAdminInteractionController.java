package kr.co.alpharking.controller.safety;

import java.util.Map;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.safety.FireSafetyAdminInteractionService;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * 1. 관리자 안전사고 상세 보기 및 안전 알림 읽음 처리.
 * 1-1. 기존 알림 API, JWT 필터, 사건 목록/상태 변경 API는 수정하지 않습니다.
 */
@RestController
@RequestMapping("/api/admin")
public class FireSafetyAdminInteractionController {
    private final FireSafetyAdminInteractionService service;

    public FireSafetyAdminInteractionController(FireSafetyAdminInteractionService service) {
        this.service = service;
    }

    /** 2. 관련 사건 상세: 모든 인증된 ADMIN이 안전 사건을 확인할 수 있습니다. */
    @GetMapping("/safety-incidents/{incidentId}")
    public Map<String, Object> incidentDetail(@PathVariable("incidentId") Long incidentId) {
        requireAdminId();
        return service.incidentDetail(incidentId);
    }

    /** 3. 안전 알림 읽음: 해당 알림을 받은 관리자 본인만 처리할 수 있습니다. */
    @PatchMapping("/safety-notifications/{notificationId}/read")
    public Map<String, Object> readNotification(@PathVariable("notificationId") Long notificationId) {
        return service.readNotification(notificationId, requireAdminId());
    }

    /** 4. 관리자 ID를 요청 값에서 받지 않고, JWT 검증 후 생성된 인증 주체에서 가져옵니다. */
    private static long requireAdminId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()
                || !(auth.getPrincipal() instanceof Admin admin)
                || admin.getAdmin_id() == null
                || admin.getAdmin_id() <= 0
                || auth.getAuthorities().stream()
                    .noneMatch(a -> "ADMIN".equals(a.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 인증이 필요합니다.");
        }
        return admin.getAdmin_id();
    }
}
