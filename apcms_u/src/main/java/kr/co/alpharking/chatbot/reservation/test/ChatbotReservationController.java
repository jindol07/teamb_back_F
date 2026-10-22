
package kr.co.alpharking.chatbot.reservation.test;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.entity.reservation.Reservation;
import kr.co.alpharking.security.Office;

@RestController
@RequestMapping("/api/chatbot/reservations")
public class ChatbotReservationController {

    @Autowired
    private ChatbotReservationService chatbotReservationService;

    // GET /api/chatbot/reservations: ID를 요청받지 않고 인증된 본인 예약만 조회합니다.
    @GetMapping
    public List<Reservation> getMyReservations(Authentication authentication) {
        return chatbotReservationService.getReservations(officeId(authentication));
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
