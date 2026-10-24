package kr.co.alpharking.dto.safety;

import com.fasterxml.jackson.annotation.JsonProperty;

/** resolution_note는 RESOLVED로 전환할 때 필수이며 최대 500 BYTE입니다. */
public record FireSafetyStatusRequest(
        @JsonProperty("status") String status,
        @JsonProperty("resolution_note") String resolutionNote) {
}
