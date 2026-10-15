package kr.co.alpharking.dto.parking;

/** 저장 버튼을 누른 시점에만 전달하는 관리자의 강제 변경 요청. */
public record ParkingSpaceUpdateRequest(
        String spaceStatusCode,
        String spaceTypeCode,
        String memo,
        String changeReason
) {}
