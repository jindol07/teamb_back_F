package kr.co.alpharking.controller.reservation;

import java.util.List;

import jakarta.validation.Valid;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.reservation.ReservationReq;
import kr.co.alpharking.dto.reservation.ReservationRes;
import kr.co.alpharking.service.reservation.ReservationService;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/reservation")
@RequiredArgsConstructor
public class ReservationController {

    private final ReservationService reservationService;

    /**
     * 예약 등록
     * POST /api/reservation
     */
    @PostMapping
    public ResponseEntity<ReservationRes> createReservation(
            @Valid @RequestBody ReservationReq request) {

        ReservationRes createdReservation =
                reservationService.createReservation(
                        request.getParkingSpaceId(),
                        request.getVehicleId(),
                        request.getVehicleNumber(),
                        request.getReservationTypeCode(),
                        request.getStartDateStr(),
                        request.getEndDateStr()
                );

        return ResponseEntity.ok(createdReservation);
    }

    /**
     * 전체 예약 조회
     * GET /api/reservation
     */
    @GetMapping
    public ResponseEntity<List<ReservationRes>> getAllReservations() {
        return ResponseEntity.ok(
                reservationService.getAllReservations());
    }
}