/** [1023_1010] 파일 안내
 * 용도: AI 통과·매칭 요청 JSON 계약.
 * 사용처·연결: AiVehicleEventController → AiVehicleEventService.
 * 통과는 direction, 매칭은 spaceCode·method를 사용한다. 필수 조합과 범위 검증은 서비스가 담당한다.
 */
package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;
import com.fasterxml.jackson.annotation.JsonProperty;

public record AiVehicleEventRequest(
 @JsonProperty("event_id") String eventId,
 @JsonProperty("event_type") String eventType,
 @JsonProperty("detected_at") String detectedAt,
 @JsonProperty("camera_id") String cameraId,
 @JsonProperty("direction") String direction,
 @JsonProperty("plate_number") String plateNumber,
 @JsonProperty("space_code") String spaceCode,
 @JsonProperty("confidence") BigDecimal confidence,
 @JsonProperty("method") String method,
 @JsonProperty("expected_parking_usage_id") Long expectedParkingUsageId
) {
 // 1. 기존 입출차 호출의 생성자 호환성을 유지합니다.
 public AiVehicleEventRequest(String eventId, String eventType, String detectedAt, String cameraId,
     String direction, String plateNumber, String spaceCode, BigDecimal confidence, String method) {
  this(eventId, eventType, detectedAt, cameraId, direction, plateNumber, spaceCode, confidence, method, null);
 }
}
