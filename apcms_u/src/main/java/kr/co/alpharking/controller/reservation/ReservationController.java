package kr.co.alpharking.controller.reservation;

import java.util.List;

import jakarta.validation.Valid;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.reservation.ReservationReq;
import kr.co.alpharking.dto.reservation.ReservationRes;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.service.reservation.ReservationService;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/reservation") 
@RequiredArgsConstructor
public class ReservationController {

    private final ReservationService reservationService;

    /**
     * 예약 등록
     * POST /alpharking/api/reservation
     */
    @PostMapping
    public ResponseEntity<ReservationRes> createReservation(
            Authentication authentication,
            @Valid @RequestBody ReservationReq request) {

        Office office = (Office) authentication.getPrincipal();

        ReservationRes createdReservation =
                reservationService.createReservation(
                        office.getOffice_id(),
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
     * GET /alpharking/api/reservation
     */
    @GetMapping
    public ResponseEntity<List<ReservationRes>> getAllReservations(Authentication authentication) {
        Office office = (Office) authentication.getPrincipal();
        return ResponseEntity.ok(
                reservationService.getReservationsByOfficeId(office.getOffice_id()));
    }

    /**
     * 선택 기간에 예약 가능한 주차 공간 조회
     * GET /alpharking/api/reservation/availability
     */
    @GetMapping("/availability")
    public ResponseEntity<List<Long>> getAvailableSpaceIds(
            @RequestParam("start_date_str") String startDateStr,
            @RequestParam("end_date_str") String endDateStr) {
        return ResponseEntity.ok(
                reservationService.getAvailableSpaceIds(startDateStr, endDateStr));
    }

    /**
     * 예약 취소 (삭제)
     * DELETE /alpharking/api/reservation/{id}
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> cancelReservation(@PathVariable("id") Long id) {
        reservationService.cancelReservation(id);
        return ResponseEntity.ok().build();
    }
}
