package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;
import lombok.Data;

/** 사용자 공개용 DTO. 관리자 메모와 차량번호를 반환하지 않음. */
@Data
public class ParkingSpacePublicRow {
    private Long parkingSpaceId;
    private Integer floorNo;
    private String floorName;
    private String zoneCode;
    private String spaceNumber;
    private String spaceTypeCode;
    private String spaceStatusCode;
    private BigDecimal xPosition;
    private BigDecimal yPosition;
    private BigDecimal width;
    private BigDecimal height;
    private String spaceCode;
    private String updatedAt;
}
