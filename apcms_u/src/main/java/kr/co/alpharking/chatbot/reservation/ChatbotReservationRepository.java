
package kr.co.alpharking.chatbot.reservation;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import kr.co.alpharking.entity.reservation.Reservation;

public interface ChatbotReservationRepository
        extends JpaRepository<Reservation, Long> {

    // 특정 오피스의 예약 내역을 생성 시각 최신순으로 조회
    List<Reservation> findByOfficeIdOrderByCreatedAtDesc(
            Long officeId
    );
}
