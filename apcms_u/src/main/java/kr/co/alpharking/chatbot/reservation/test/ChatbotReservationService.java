
package kr.co.alpharking.chatbot.reservation.test;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.entity.reservation.Reservation;

@Service
@Transactional(readOnly = true)
public class ChatbotReservationService {

    @Autowired
    private ChatbotReservationRepository chatbotReservationRepository;

    public List<Reservation> getReservations(Long officeId) {

        return chatbotReservationRepository
                .findByOfficeIdOrderByCreatedAtDesc(officeId);
    }
}
