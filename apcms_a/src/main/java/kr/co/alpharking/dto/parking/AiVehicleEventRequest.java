/** 파일 안내
 * 용도: AI 통과·매칭 요청 JSON 계약.
 * 사용처·연결: AiVehicleEventController → AiVehicleEventService.
 * 통과는 direction, 매칭은 spaceCode·method를 사용한다. 필수 조합과 범위 검증은 서비스가 담당한다.
 */
package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;
import com.fasterxml.jackson.annotation.JsonProperty;

public record AiVehicleEventRequest(
 // 이벤트 UUID. 형식 확인과 영속 중복 처리 보장은 서로 다른 책임이다.
 @JsonProperty("event_id") String eventId,
 // 통과는 VEHICLE_PASSAGE, 구획 매칭은 VEHICLE_SPACE_MATCH다.
 @JsonProperty("event_type") String eventType,
 // 시간대 오프셋을 포함한 감지 시각. 서비스가 실제 순간 검사 후 한국 시각으로 저장한다.
 @JsonProperty("detected_at") String detectedAt,
 // 이벤트를 관찰한 카메라 식별자.
 @JsonProperty("camera_id") String cameraId,
 // 통과 이벤트의 ENTRY 또는 EXIT. 구획 매칭에서는 전달하지 않는다.
 @JsonProperty("direction") String direction,
 // 인식 차량번호. 서비스에서 공백 제거와 국내 번호판 형식 검사를 수행한다.
 @JsonProperty("plate_number") String plateNumber,
 // 구획 매칭 대상 코드. 통과 이벤트에는 포함하지 않는다.
 @JsonProperty("space_code") String spaceCode,
 // 인식 신뢰도. 서비스가 0 이상 1 이하인지 검사한다.
 @JsonProperty("confidence") BigDecimal confidence,
 // 매칭 근거 TRACKING 또는 PLATE_OCR. 필수 조합은 서비스가 검증한다.
 @JsonProperty("method") String method,
 @JsonProperty("expected_parking_usage_id") Long expectedParkingUsageId
) {
 // 1. 기존 입출차 호출의 생성자 호환성을 유지합니다.
 public AiVehicleEventRequest(String eventId, String eventType, String detectedAt, String cameraId,
     String direction, String plateNumber, String spaceCode, BigDecimal confidence, String method) {
  this(eventId, eventType, detectedAt, cameraId, direction, plateNumber, spaceCode, confidence, method, null);
 }
}
