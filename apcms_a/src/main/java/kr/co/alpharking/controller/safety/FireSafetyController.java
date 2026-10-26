package kr.co.alpharking.controller.safety;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import java.util.Map;
import kr.co.alpharking.dao.safety.FireSafetyDao;
import kr.co.alpharking.dto.safety.FireSafetyRequest;
import kr.co.alpharking.dto.safety.FireSafetyResponse;
import kr.co.alpharking.service.safety.FireSafetyIngest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class FireSafetyController {
    private final FireSafetyIngest service;
    private final FireSafetyDao dao;
    private final String apiKey;

    public FireSafetyController(FireSafetyIngest service, FireSafetyDao dao,
            @Value("${FIRE_ALERT_API_KEY:}") String apiKey) {
        this.service = service; this.dao = dao; this.apiKey = apiKey;
    }

    /** Python의 Bearer 공유키는 별도 Spring Security 체인에서 전달된 후 여기서 검증합니다. */
    @PostMapping("/api/parking/ai/fire-alerts")
    public FireSafetyResponse accept(
            @RequestHeader(value = "Authorization", required = false) String authorization,
            @RequestHeader(value = "X-Idempotency-Key", required = false) String idempotency,
            @RequestBody FireSafetyRequest request) {
        if (apiKey == null || apiKey.length() < 24)
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                "FIRE_ALERT_API_KEY에 충분한 길이의 공유키를 설정하세요.");
        String provided = authorization != null && authorization.startsWith("Bearer ")
                ? authorization.substring(7) : "";
        if (!MessageDigest.isEqual(apiKey.getBytes(StandardCharsets.UTF_8),
                provided.getBytes(StandardCharsets.UTF_8)))
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "AI 공유키 불일치");
        return service.receive(request, idempotency);
    }

    /** 관리자 JWT에 ADMIN 권한이 있어야만 목록을 조회할 수 있습니다. */
    @GetMapping("/api/admin/safety-incidents")
    public List<Map<String, Object>> recent(@RequestParam(name = "limit", defaultValue = "30") int limit) {
        Authentication user = SecurityContextHolder.getContext().getAuthentication();
        if (user == null || !user.isAuthenticated()
                || user.getAuthorities().stream().noneMatch(a -> "ADMIN".equals(a.getAuthority())))
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        if (limit < 1 || limit > 100)
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "limit은 1~100이어야 합니다.");
        return dao.recent(limit);
    }
}
