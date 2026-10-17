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
