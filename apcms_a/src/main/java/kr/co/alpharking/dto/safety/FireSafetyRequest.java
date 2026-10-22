package kr.co.alpharking.dto.safety;

import java.math.BigDecimal;
import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;

/** ai_vision.safety.fire_alert_sender 의 JSON v1 형식을 변경 없이 수신합니다. */
public record FireSafetyRequest(
    @JsonProperty("schema_version") String schemaVersion,
    @JsonProperty("transition_id") String transitionId,
    @JsonProperty("incident_id") String incidentId,
    @JsonProperty("region_id") String regionId,
    @JsonProperty("hazard_type") String hazardType,
    @JsonProperty("status") String status,
    @JsonProperty("observed_at_utc") String observedAtUtc,
    @JsonProperty("source_seconds") BigDecimal sourceSeconds,
    @JsonProperty("frame_index") Long frameIndex,
    @JsonProperty("confidence") BigDecimal confidence,
    @JsonProperty("bbox_xyxy") List<Integer> bboxXyxy,
    @JsonProperty("hits_in_window") Long hitsInWindow,
    @JsonProperty("reason") String reason,
    @JsonProperty("source") Source source,
    @JsonProperty("session_started_at_utc") String sessionStartedAtUtc,
    @JsonProperty("is_test") Boolean isTest,
    @JsonProperty("requires_human_review") Boolean requiresHumanReview
) {
    public record Source(@JsonProperty("kind") String kind,
                         @JsonProperty("name") String name) {}
}
