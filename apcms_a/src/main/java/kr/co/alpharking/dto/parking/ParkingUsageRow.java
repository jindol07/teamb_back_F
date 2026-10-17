package kr.co.alpharking.dto.parking;

import lombok.Data;

@Data
public class ParkingUsageRow {
    private Long parkingUsageId;
    private Long vehicleId;
    private String vehicleNumber;
    private Long parkingSpaceId;
    private String spaceCode;
    private String entryAt;
    private String exitAt;
    private String parkingTypeCode;
}
