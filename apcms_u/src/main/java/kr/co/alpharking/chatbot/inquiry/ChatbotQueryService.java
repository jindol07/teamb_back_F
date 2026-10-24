package kr.co.alpharking.chatbot.inquiry;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
public class ChatbotQueryService {
    private final ChatbotQueryRepository1024 repository;

    public ChatbotQueryService(ChatbotQueryRepository1024 repository) {
        this.repository = repository;
    }

    public List<ChatbotQueryRepository1024.UsageRow> usage(long officeId) {
        return repository.findUsage(officeId);
    }

    public List<ChatbotQueryRepository1024.ReservationRow> reservations(long officeId) {
        return repository.findReservations(officeId);
    }

    public List<ChatbotQueryRepository1024.VehicleRow> vehicles(long officeId) {
        return repository.findVehicles(officeId);
    }
}
