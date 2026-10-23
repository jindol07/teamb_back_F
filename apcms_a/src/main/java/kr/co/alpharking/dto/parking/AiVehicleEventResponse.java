/** [1023_1010] 파일 안내
 * 용도: AI 통과·매칭 처리 결과 응답.
 * 사용처·연결: AiVehicleEventService → AiVehicleEventController → 외부 AI 송신기.
 * PENDING은 조건 부족·배정 충돌로 보류한 결과다. UNCHANGED는 이미 반영된 상태를 나타낸다.
 */
package kr.co.alpharking.dto.parking;

public record AiVehicleEventResponse(String eventId, String eventType, String outcome,
                                     String plateNumber, String spaceCode,
                                     Long parkingUsageId, String detail) {}
