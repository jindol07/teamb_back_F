package kr.co.alpharking.dto.vehicle;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class VehicleSaveRequestDto {
    private Long officeId;
    private String vehicleNumber;
    private String aliasName;
}