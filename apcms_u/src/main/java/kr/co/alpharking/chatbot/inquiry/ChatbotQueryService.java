package kr.co.alpharking.chatbot.inquiry;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
public class ChatbotQueryService {
    private final ChatbotQueryRepository repository;

    public ChatbotQueryService(ChatbotQueryRepository repository) {
        this.repository = repository;
    }

    public List<ChatbotQueryRepository.UsageRow> usage(long officeId) {
        return repository.findUsage(officeId);
    }

    public List<ChatbotQueryRepository.ReservationRow> reservations(long officeId) {
        return repository.findReservations(officeId);
    }

    public List<ChatbotQueryRepository.VehicleRow> vehicles(long officeId) {
        return repository.findVehicles(officeId);
    }
}
