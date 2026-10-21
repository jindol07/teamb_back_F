package kr.co.alpharking.dto.reservation;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class ReservationReq {

    @NotNull(message = "주차 공간 ID는 필수 입력값입니다.")
    private Long parkingSpaceId;

    private Long vehicleId;

    @NotBlank(message = "차량 번호는 필수 입력값입니다.")
    private String vehicleNumber;

    @NotBlank(message = "예약 타입 코드는 필수 입력값입니다.")
    private String reservationTypeCode;

    @NotBlank(message = "시작일은 필수 입력값입니다.")
    private String startDateStr;

    @NotBlank(message = "종료일은 필수 입력값입니다.")
    private String endDateStr;
}
