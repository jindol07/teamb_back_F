package kr.co.alpharking.recmnTest;

// 추천된 주차 공간 정보
public record ParkingRecommendationResponse(
        Long parkingSpaceId,
        Integer floorNo,
        String zoneCode,
        Integer spaceNumber
) {
}