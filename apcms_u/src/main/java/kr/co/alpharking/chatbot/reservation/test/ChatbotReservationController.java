
package kr.co.alpharking.chatbot.reservation.test;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.entity.reservation.Reservation;

@RestController
@RequestMapping("/api/chatbot/reservations")
public class ChatbotReservationController {

    @Autowired
    private ChatbotReservationService chatbotReservationService;

    // 특정 오피스의 예약 내역 조회 로그인 성공시 API로 교체
    // GET /api/chatbot/reservations/1
    @GetMapping("/{officeId}")
    public List<Reservation> getReservationsByOfficeId(
            @PathVariable("officeId") Long officeId) {

        return chatbotReservationService.getReservations(officeId);
    }
}
