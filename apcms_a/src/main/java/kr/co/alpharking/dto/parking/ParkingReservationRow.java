package kr.co.alpharking.dto.parking;

import lombok.Data;

/** 관리자 전용 예약 조회 응답. 기존 예약 테이블을 읽기만 한다. */
@Data
public class ParkingReservationRow {
    private Long parkingReservationId;
    private Long parkingSpaceId;
    private String vehicleNumber;
    private String reservationStartAt;
    private String reservationEndAt;
    private String statusCode;
}
