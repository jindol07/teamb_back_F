package kr.co.alpharking.dto.parking;

/** 관리자 전용 판정 이력. 현재 점유 상태나 위반 확정 기록과 구분합니다. */
public record AiParkingDecisionRow(Long aiDetectionEventId, String eventId, String detectedAt,
    String cameraId, String plateNumber, String spaceCode, Long parkingUsageId,
    Long expectedParkingUsageId, String parkingDecision, String outcome) {}
