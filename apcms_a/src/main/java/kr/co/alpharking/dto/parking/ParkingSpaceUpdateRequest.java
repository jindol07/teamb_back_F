package kr.co.alpharking.dto.parking;

import java.util.List;

/** 저장 버튼을 누른 시점에만 전달하는 관리자의 강제 변경 요청. */
public record ParkingSpaceUpdateRequest(
        String spaceStatusCode,
        String spaceTypeCode,
        String memo,
        String changeReason,
        String usageAction,
        Long parkingUsageId,
        String vehicleNumber,
        String exitAt,
        String expectedStatus,
        String expectedType,
        String expectedMemo,
        String expectedUpdatedAt,
        Long expectedHistoryId,
        List<Long> expectedActiveUsageIds
) {}
