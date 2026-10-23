/** [1023_1010] 파일 안내
 * 용도: AI 점유 요청 JSON 계약.
 * 사용처·연결: AiOccupancyController.accept → AiOccupancyService.receive.
 * @JsonProperty가 snake_case JSON과 Java record 접근자를 연결한다. 감지 시각은 오프셋 포함 문자열이다.
 */
package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;
import com.fasterxml.jackson.annotation.JsonProperty;

/** FastAPI 주차구획 점유 이벤트 수신 계약. */
public record AiOccupancyRequest(
        @JsonProperty("event_id") String eventId,
        @JsonProperty("event_type") String eventType,
        @JsonProperty("detected_at") String detectedAt,
        @JsonProperty("space_code") String spaceCode,
        @JsonProperty("status") String status,
        @JsonProperty("change_ratio") BigDecimal changeRatio,
        @JsonProperty("source") String source) {}
