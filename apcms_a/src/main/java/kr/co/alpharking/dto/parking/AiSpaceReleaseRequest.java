package kr.co.alpharking.dto.parking;

import com.fasterxml.jackson.annotation.JsonProperty;

/** 연결 성공 응답에서 받은 이용 ID·버전으로만 기존 연결을 해제한다. */
public record AiSpaceReleaseRequest(
    @JsonProperty("event_id") String eventId,
    @JsonProperty("event_type") String eventType,
    @JsonProperty("detected_at") String detectedAt,
    @JsonProperty("camera_id") String cameraId,
    @JsonProperty("plate_number") String plateNumber,
    @JsonProperty("space_code") String spaceCode,
    @JsonProperty("parking_usage_id") Long parkingUsageId,
    @JsonProperty("link_version") Long linkVersion,
    @JsonProperty("reason") String reason
) {}
