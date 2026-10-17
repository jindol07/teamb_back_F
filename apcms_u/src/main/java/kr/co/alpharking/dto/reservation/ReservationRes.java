package kr.co.alpharking.dto.reservation;

import java.time.LocalDateTime;

import kr.co.alpharking.entity.reservation.Reservation;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ReservationRes {
    private Long parkingReservationId;
    private Long officeId;
    private Long parkingSpaceId;
    private Long vehicleId;
    private String vehicleNumber;
    private String reservationTypeCode;
    private LocalDateTime reservationStartAt;
    private LocalDateTime reservationEndAt;
    private String statusCode;
    private String recommendedYn;
    private LocalDateTime createdAt;

    // Entity -> DTO 변환을 위한 정적 팩토리 메서드
    public static ReservationRes from(Reservation reservation) {
        return ReservationRes.builder()
                .parkingReservationId(reservation.getParkingReservationId())
                .officeId(reservation.getOfficeId())
                .parkingSpaceId(reservation.getParkingSpaceId())
                .vehicleId(reservation.getVehicleId())
                .vehicleNumber(reservation.getVehicleNumber())
                .reservationTypeCode(reservation.getReservationTypeCode())
                .reservationStartAt(reservation.getReservationStartAt())
                .reservationEndAt(reservation.getReservationEndAt())
                .statusCode(reservation.getStatusCode())
                .recommendedYn(reservation.getRecommendedYn())
                .createdAt(reservation.getCreatedAt())
                .build();
    }
}