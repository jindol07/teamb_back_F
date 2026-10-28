/** 파일 안내
 * 용도: AI 점유 처리 결과 응답.
 * 사용처·연결: AiOccupancyService → AiOccupancyController → 외부 AI 송신기.
 * outcome·이전/현재 상태·저장 이벤트 ID를 반환한다. 중복 결과의 이벤트 ID는 null이다.
 * UPDATED만 상태 변경을 뜻한다. DUPLICATE·UNCHANGED·SKIPPED 결과는 이전 상태를 유지한다.
 */
package kr.co.alpharking.dto.parking;

public record AiOccupancyResponse(String eventId, String spaceCode, String outcome,
                                  String previousStatus, String currentStatus,
                                  Long aiDetectionEventId) {}
