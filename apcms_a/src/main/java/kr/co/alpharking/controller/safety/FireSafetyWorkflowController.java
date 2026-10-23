package kr.co.alpharking.controller.safety;

import java.util.Map;
import kr.co.alpharking.dto.safety.FireSafetyStatusRequest;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.safety.FireSafetyWorkflowService;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/** 기존 팀원 알림/보안 Controller 수정 없이 사건 업무 상태만 변경합니다. */
@RestController
@RequestMapping("/api/admin/safety-incidents")
public class FireSafetyWorkflowController {
    private final FireSafetyWorkflowService service;

    public FireSafetyWorkflowController(FireSafetyWorkflowService service) {
        this.service = service;
    }

    @PatchMapping("/{incidentId}/status")
    public Map<String, Object> changeStatus(@PathVariable("incidentId") Long incidentId,
                                             @RequestBody FireSafetyStatusRequest request) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()
                || auth.getAuthorities().stream().noneMatch(a -> "ADMIN".equals(a.getAuthority()))
                || !(auth.getPrincipal() instanceof Admin admin)
                || admin.getAdmin_id() == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 인증이 필요합니다.");
        }
        if (request == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 본문이 필요합니다.");
        }
        // 관리자 ID는 Body/URL에서 받지 않고 JWT 인증 객체에서만 가져옵니다.
        return service.change(incidentId, admin.getAdmin_id(), request.status(), request.resolutionNote());
    }
}
