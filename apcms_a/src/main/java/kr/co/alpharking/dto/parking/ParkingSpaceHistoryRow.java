package kr.co.alpharking.dto.parking;

import lombok.Data;

/** 관리자 패널 전용 구획 이력. 기존 테이블을 조회하며 스키마를 추가하지 않는다. */
@Data
public class ParkingSpaceHistoryRow {
    private Long parkingSpaceHistoryId;
    private String spaceStatusCode;
    private String spaceTypeCode;
    private String memo;
    private String changeReason;
    private Long changedByAdminId;
    private String changeSourceCode;
    private String validFrom;
    private String validTo;
}
