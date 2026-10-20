package kr.co.alpharking.chatbot.inquiry;

import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.security.Office;

@RestController
@RequestMapping("/api/chatbot/conversations")
public class ChatbotConversationController {
    private final ChatbotConversationService service;
    public ChatbotConversationController(ChatbotConversationService service) { this.service = service; }

    @PostMapping("/exchanges")
    public ChatbotConversationService.Saved save(Authentication authentication,
            @Valid @RequestBody ChatbotConversationService.SaveRequest request) {
        return service.save(officeId(authentication), request);
    }

    @GetMapping("/latest")
    public ChatbotConversationService.History latest(Authentication authentication) {
        return service.latest(officeId(authentication));
    }

    @GetMapping("/{id}/messages")
    public ChatbotConversationService.History messages(Authentication authentication, @PathVariable("id") String id) {
        return service.history(officeId(authentication), id);
    }

    private long officeId(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다.");
        }
        if (!(authentication.getPrincipal() instanceof Office office) || office.getOffice_id() == null
                || authentication.getAuthorities().stream().noneMatch(role -> "OFFICE".equals(role.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "사용자 계정으로 로그인해 주세요.");
        }
        return office.getOffice_id();
    }
}
