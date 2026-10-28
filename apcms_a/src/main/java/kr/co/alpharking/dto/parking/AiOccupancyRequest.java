/** 파일 안내
 * 용도: AI 점유 요청 JSON 계약.
 * 사용처·연결: AiOccupancyController.accept → AiOccupancyService.receive.
 * @JsonProperty가 snake_case JSON과 Java record 접근자를 연결한다. 감지 시각은 오프셋 포함 문자열이다.
 */
package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;
import com.fasterxml.jackson.annotation.JsonProperty;

/** FastAPI 주차구획 점유 이벤트 수신 계약. */
public record AiOccupancyRequest(
        // 송신 이벤트 UUID. 같은 구획의 기존 payload와 대조해 재전송을 확인한다.
        @JsonProperty("event_id") String eventId,
        // 이 API가 받는 이벤트 유형은 PARKING_OCCUPANCY다.
        @JsonProperty("event_type") String eventType,
        // UTC의 Z 또는 시간대 오프셋을 포함한 감지 시각. 서비스가 DB용 한국 시각으로 변환한다.
        @JsonProperty("detected_at") String detectedAt,
        // AI와 도면이 공유하는 층·구역·구획 코드. 예: 1F-A01.
        @JsonProperty("space_code") String spaceCode,
        // AI 감지 결과인 OCCUPIED 또는 AVAILABLE. 차량번호와의 연결 결과는 아니다.
        @JsonProperty("status") String status,
        // 0 이상 1 이하의 변화 비율. 정밀도를 보존하기 위해 BigDecimal로 받는다.
        @JsonProperty("change_ratio") BigDecimal changeRatio,
        // 이 계약에서 허용하는 변경 출처는 AI다.
        @JsonProperty("source") String source) {}
