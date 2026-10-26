package kr.co.alpharking.dto.vehicle;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class VehicleRegistrationRequestDto {
    private String vehicleNumber;
    private String ownerName; // 차주명 추가
    private String vehicleModel;
}
