package kr.co.alpharking.chatbot.inquiry;

import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.security.Office;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

/** 기존 예약/차량 API는 유지하고, 챗봇에는 인증된 본인 데이터만 제공합니다. */
@RestController
@RequestMapping("/api/chatbot/me")
public class ChatbotQueryController {
    private final ChatbotQueryService service;

    public ChatbotQueryController(ChatbotQueryService service) {
        this.service = service;
    }

    // 공통 SNAKE_CASE는 유지하고 챗봇 API 계약의 officeId 이름을 명시합니다.
    @JsonNaming(PropertyNamingStrategies.LowerCamelCaseStrategy.class)
    public record Profile(long officeId) {}

    @GetMapping
    public Profile me(Authentication authentication) {
        return new Profile(officeId(authentication));
    }

    @GetMapping("/usage")
    public List<ChatbotQueryRepository1024.UsageRow> usage(Authentication authentication) {
        return service.usage(officeId(authentication));
    }

    @GetMapping("/reservations")
    public List<ChatbotQueryRepository1024.ReservationRow> reservations(Authentication authentication) {
        return service.reservations(officeId(authentication));
    }

    @GetMapping("/vehicles")
    public List<ChatbotQueryRepository1024.VehicleRow> vehicles(Authentication authentication) {
        return service.vehicles(officeId(authentication));
    }

    private long officeId(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다.");
        }
        if (!(authentication.getPrincipal() instanceof Office office)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "인증된 사용자 객체가 Office 타입이 아닙니다.");
        }
        if (office.getOffice_id() == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "인증된 Office에 사용자 ID가 없습니다.");
        }
        if (authentication.getAuthorities().stream().noneMatch(role -> "OFFICE".equals(role.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "인증된 계정에 OFFICE 권한이 없습니다.");
        }
        // details는 요청 부가 정보입니다. 사용자 ID는 인증된 Office에서 가져옵니다.
        return office.getOffice_id();
    }

    // /error 재전송으로 원래 인증 오류가 가려지지 않도록 안전한 진단 코드만 반환합니다.
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, String>> authenticationError(ResponseStatusException exception) {
        return ResponseEntity.status(exception.getStatusCode()).body(Map.of(
                "code", "CHATBOT_IDENTITY_CHECK", "detail", exception.getReason()));
    }
}
