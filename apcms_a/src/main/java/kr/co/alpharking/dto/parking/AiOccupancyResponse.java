/** [1023_1010] 파일 안내
 * 용도: AI 점유 처리 결과 응답.
 * 사용처·연결: AiOccupancyService → AiOccupancyController → 외부 AI 송신기.
 * outcome·이전/현재 상태·저장 이벤트 ID를 반환한다. 중복 등 결과에 따라 이벤트 ID는 null일 수 있다.
 */
package kr.co.alpharking.dto.parking;

public record AiOccupancyResponse(String eventId, String spaceCode, String outcome,
                                  String previousStatus, String currentStatus,
                                  Long aiDetectionEventId) {}
