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
    private BigDecimal width;
    private BigDecimal height;
    private String spaceCode;
    /** 관리자 전용 차량번호. 미출차 기록이 정확히 한 건 매칭될 때만 제공. */
    private String vehicleNumber;
    private String memo;
    private String updatedAt;
}
