package kr.co.alpharking.repository.reservation;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import kr.co.alpharking.entity.reservation.ReservationHistory;

@Repository
public interface ReservationHistoryRepository extends JpaRepository<ReservationHistory, Long>{

}