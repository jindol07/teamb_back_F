package kr.co.alpharking.dto.safety;

import com.fasterxml.jackson.annotation.JsonProperty;

/** status만으로 처리 완료할 수 있다. 기존 클라이언트의 resolution_note는 선택이며 최대 500 BYTE다. */
public record FireSafetyStatusRequest(
        @JsonProperty("status") String status,
        @JsonProperty("resolution_note") String resolutionNote) {
}
