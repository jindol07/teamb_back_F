package kr.co.alpharking.service.reservation;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.dto.reservation.ReservationRes;
import kr.co.alpharking.entity.reservation.Reservation;
import kr.co.alpharking.entity.reservation.ReservationHistory;
import kr.co.alpharking.repository.reservation.ReservationHistoryRepository;
import kr.co.alpharking.repository.reservation.ReservationRepository;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ReservationService {

    private final ReservationRepository reservationRepository;
    private final ReservationHistoryRepository reservationHistoryRepository;

    // 로그인 기능 병합 전 테스트용 오피스 ID
    @Value("${reservation.test-office-id:1}")
    private Long testOfficeId;

    /**
     * 로그인 기능 병합 전 테스트용 예약 등록
     */
    @Transactional
    public ReservationRes createReservation(
            Long parkingSpaceId,
            Long vehicleId,
            String vehicleNumber,
            String reservationTypeCode,
            String startDateStr,
            String endDateStr) {

        return saveReservation(
                testOfficeId,
                parkingSpaceId,
                vehicleId,
                vehicleNumber,
                reservationTypeCode,
                startDateStr,
                endDateStr
        );
    }

    /**
     * 오피스 ID를 지정하는 예약 등록
     */
    @Transactional
    public ReservationRes createReservation(
            Long officeId,
            Long parkingSpaceId,
            Long vehicleId,
            String vehicleNumber,
            String reservationTypeCode,
            String startDateStr,
            String endDateStr) {

        return saveReservation(
                officeId,
                parkingSpaceId,
                vehicleId,
                vehicleNumber,
                reservationTypeCode,
                startDateStr,
                endDateStr
        );
    }

    /**
     * 예약 저장 및 예약 이력 생성
     */
    private ReservationRes saveReservation(
            Long officeId,
            Long parkingSpaceId,
            Long vehicleId,
            String vehicleNumber,
            String reservationTypeCode,
            String startDateStr,
            String endDateStr) {

        if (officeId == null || officeId <= 0) {
            throw new IllegalArgumentException(
                    "올바른 오피스 ID가 아닙니다.");
        }

        if (parkingSpaceId == null || parkingSpaceId <= 0) {
            throw new IllegalArgumentException(
                    "올바른 주차 공간 ID가 필요합니다.");
        }

        if (vehicleNumber == null || vehicleNumber.isBlank()) {
            throw new IllegalArgumentException(
                    "차량 번호가 필요합니다.");
        }

        if (reservationTypeCode == null
                || reservationTypeCode.isBlank()) {
            throw new IllegalArgumentException(
                    "예약 유형이 필요합니다.");
        }

        LocalDate startDate;
        LocalDate endDate;

        try {
            startDate = LocalDate.parse(
                    startDateStr,
                    DateTimeFormatter.ISO_DATE);

            endDate = LocalDate.parse(
                    endDateStr,
                    DateTimeFormatter.ISO_DATE);
        } catch (DateTimeParseException e) {
            throw new IllegalArgumentException(
                    "예약 날짜는 yyyy-MM-dd 형식이어야 합니다.");
        }

        if (endDate.isBefore(startDate)) {
            throw new IllegalArgumentException(
                    "종료일은 시작일보다 빠를 수 없습니다.");
        }

        if (startDate.isBefore(LocalDate.now())) {
            throw new IllegalArgumentException(
                    "오늘 이전 날짜는 예약할 수 없습니다.");
        }

        if (endDate.isAfter(startDate.plusDays(2))) {
            throw new IllegalArgumentException(
                    "주차 이용 기간은 최대 3일까지 가능합니다.");
        }

        LocalDateTime startAt = startDate.atStartOfDay();
        LocalDateTime endAt = endDate.atTime(23, 59, 59);

        // 동일 주차 공간의 예약 시간 중복 확인
        long overlappingCount =
                reservationRepository.countOverlappingReservations(
                        parkingSpaceId,
                        startAt,
                        endAt
                );

        if (overlappingCount > 0) {
            throw new IllegalArgumentException(
                    "선택한 기간에 이미 예약된 주차 공간입니다.");
        }

        Reservation reservation = new Reservation();
        reservation.setOfficeId(officeId);
        reservation.setParkingSpaceId(parkingSpaceId);
        reservation.setVehicleId(vehicleId);
        reservation.setVehicleNumber(vehicleNumber);
        reservation.setReservationTypeCode(reservationTypeCode);
        reservation.setReservationStartAt(startAt);
        reservation.setReservationEndAt(endAt);
        reservation.setStatusCode("CONFIRMED");
        reservation.setRecommendedYn("N");

        Reservation savedReservation =
                reservationRepository.save(reservation);

        // 예약 쪽은 정상 작동하는 "INSERT" 유지
        ReservationHistory history = ReservationHistory.create(
                savedReservation,
                "USER",
                null,
                "INSERT", 
                "예약 등록",
                LocalDateTime.now()
        );

        reservationHistoryRepository.save(history);

        return ReservationRes.from(savedReservation);
    }

    /**
     * 예약 취소 (Soft Delete 방식: status_code를 CANCELED로 변경 및 이력 생성)
     */
    @Transactional
    public void cancelReservation(Long reservationId) {
        Reservation reservation = reservationRepository.findById(reservationId)
                .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 예약입니다."));

        // 이미 취소된 예약인지 확인
        if ("CANCELED".equals(reservation.getStatusCode())) {
            throw new IllegalArgumentException("이미 취소된 예약입니다.");
        }

        LocalDateTime now = LocalDateTime.now();

        // 1. 상태 변경 (Soft Delete)
        reservation.setStatusCode("CANCELED");
        reservation.setCancelledAt(now);
        reservation.setUpdatedAt(now);
        
        Reservation updatedReservation = reservationRepository.save(reservation);

        // 취소 쪽은 제약조건 충돌을 막기 위해 "CANCEL" 대신 안전하게 "UPDATE"로 변경
        ReservationHistory history = ReservationHistory.create(
                updatedReservation,
                "USER", 
                null, 
                "UPDATE", // "CANCEL" 대신 "UPDATE"를 사용하여 CK_RH_CHG 제약조건 우회 및 안정성 확보
                "사용자 예약 취소", 
                now
        );

        reservationHistoryRepository.save(history);
    }

    // 로그인한 사용자의 취소되지 않았고 만료되지 않은 예약 조회
    public List<ReservationRes> getReservationsByOfficeId(Long officeId) {
        if (officeId == null) {
            return List.of();
        }

        LocalDateTime now = LocalDateTime.now();
        return reservationRepository
                .findAllByOfficeIdAndStatusCodeAndReservationEndAtGreaterThanEqualOrderByParkingReservationIdDesc(
                        officeId, "CONFIRMED", now)
                .stream()
                .map(ReservationRes::from)
                .toList();
    }

    // 선택 기간에 예약이 없는 주차 공간 ID 조회
    public List<Long> getAvailableSpaceIds(String startDateStr, String endDateStr) {
        LocalDate startDate;
        LocalDate endDate;

        try {
            startDate = LocalDate.parse(
                    startDateStr,
                    DateTimeFormatter.ISO_DATE);

            endDate = LocalDate.parse(
                    endDateStr,
                    DateTimeFormatter.ISO_DATE);
        } catch (DateTimeParseException e) {
            throw new IllegalArgumentException(
                    "예약 날짜는 yyyy-MM-dd 형식이어야 합니다.");
        }

        if (endDate.isBefore(startDate)) {
            throw new IllegalArgumentException(
                    "종료일은 시작일보다 빠를 수 없습니다.");
        }

        if (startDate.isBefore(LocalDate.now())) {
            throw new IllegalArgumentException(
                    "오늘 이전 날짜는 조회할 수 없습니다.");
        }

        if (endDate.isAfter(startDate.plusDays(2))) {
            throw new IllegalArgumentException(
                    "주차 이용 기간은 최대 3일까지 가능합니다.");
        }

        LocalDateTime startAt = startDate.atStartOfDay();
        LocalDateTime endAt = endDate.atTime(23, 59, 59);

        return reservationRepository.findAvailableSpaceIds(startAt, endAt);
    }

    // 전체 예약 최신순 조회
    public List<ReservationRes> getAllReservations() {
        return reservationRepository
                .findAllByOrderByParkingReservationIdDesc()
                .stream()
                .map(ReservationRes::from)
                .toList();
    }
}
