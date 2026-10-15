package kr.co.alpharking.controller.reservation;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.entity.reservation.ReservationHistory;
import kr.co.alpharking.service.reservation.ReservationHistoryService;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/reservation-histories")
@RequiredArgsConstructor
public class ReservationHistoryController {

    private final ReservationHistoryService reservationHistoryService;

    // 전체 예약 히스토리 조회 API
    // GET /api/reservation-histories
    @GetMapping
    public ResponseEntity<List<ReservationHistory>> getAllHistories() {
        List<ReservationHistory> histories = reservationHistoryService.getAllHistories();
        return ResponseEntity.ok(histories);
    }

    // 예약 히스토리 등록 API
    // POST /api/reservation-histories
    @PostMapping
    public ResponseEntity<ReservationHistory> createHistory(@RequestBody ReservationHistory history) {
        ReservationHistory savedHistory = reservationHistoryService.saveHistory(history);
        return ResponseEntity.ok(savedHistory);
    }
}