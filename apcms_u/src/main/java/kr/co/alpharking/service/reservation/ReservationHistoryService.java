package kr.co.alpharking.service.reservation;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.entity.reservation.ReservationHistory;
import kr.co.alpharking.repository.reservation.ReservationHistoryRepository;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ReservationHistoryService {

    private final ReservationHistoryRepository reservationHistoryRepository;

    // 예약 히스토리 단건 저장
    @Transactional
    public ReservationHistory saveHistory(ReservationHistory history) {
        return reservationHistoryRepository.save(history);
    }

    // 전체 예약 히스토리 조회
    public List<ReservationHistory> getAllHistories() {
        return reservationHistoryRepository.findAll();
    }
}