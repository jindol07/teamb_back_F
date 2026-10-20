package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;

/** 로그인한 사용자에게 제공할 주차현황. 차량번호와 관리자 메모는 포함하지 않는다. */
public record ParkingSpacePublicRow(
        Long parkingSpaceId,
        Integer floorNo,
        String floorName,
        String zoneCode,
        String spaceNumber,
        String spaceTypeCode,
        String spaceStatusCode,
        BigDecimal xPosition,
        BigDecimal yPosition,
        BigDecimal width,
        BigDecimal height,
        String spaceCode,
        String updatedAt) {}
