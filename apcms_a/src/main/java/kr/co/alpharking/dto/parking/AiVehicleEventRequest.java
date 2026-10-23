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
 @JsonProperty("method") String method
) {}
