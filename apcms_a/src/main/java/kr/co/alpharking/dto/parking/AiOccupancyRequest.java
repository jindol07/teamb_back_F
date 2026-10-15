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
