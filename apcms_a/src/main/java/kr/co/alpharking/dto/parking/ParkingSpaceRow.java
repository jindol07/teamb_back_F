package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;
import lombok.Data;

/** 관리자 조회용 구획 DTO: FLOOR -> ZONE -> SPACE. */
@Data
public class ParkingSpaceRow {
    private Long parkingSpaceId;
    private Integer floorNo;
    private String floorName;
    private String zoneCode;
    private String spaceNumber;
    private String spaceTypeCode;
    private String spaceStatusCode;
    private BigDecimal xPosition;
    private BigDecimal yPosition;
    private String memo;
    private String updatedAt;
}
