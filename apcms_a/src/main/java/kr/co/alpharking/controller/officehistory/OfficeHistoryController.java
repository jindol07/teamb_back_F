/**
 * 용도: 관리자 이력 화면의 사무실 계정 이력 조회 API.
 * 사용처: History.tsx → GET /api/office-histories → OfficeHistoryService.
 * 기존 이력만 조회하며 계정 변경이나 이력 생성은 수행하지 않는다.
 */
package kr.co.alpharking.controller.officehistory;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.officehistory.OfficeHistoryRow;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.officehistory.OfficeHistoryService;

@RestController
@RequestMapping("/api/office-histories")
public class OfficeHistoryController {
    private final OfficeHistoryService service;

    public OfficeHistoryController(OfficeHistoryService service) {
        this.service = service;
    }

    @GetMapping
    public List<OfficeHistoryRow> list(Authentication authentication) {
        // 사무실 연락처 등이 포함되므로 로그인 여부와 실제 관리자 권한을 모두 검사한다.
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        if (!(authentication.getPrincipal() instanceof Admin admin) || admin.getAdmin_id() == null
                || authentication.getAuthorities().stream()
                        .noneMatch(authority -> "ADMIN".equals(authority.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
        return service.findAll();
    }
}
