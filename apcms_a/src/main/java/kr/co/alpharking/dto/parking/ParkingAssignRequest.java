/** [1023_1010] 파일 안내
 * 용도: 기존 이용 기록에 연결할 구획 ID를 받는 수동 배정 요청.
 * 사용처·연결: ParkingUsageController.assign의 PATCH /api/parking/usages/{id}/space.
 * parkingSpaceId는 PARKING_SPACE의 숫자 PK다. 삭제하면 Controller 요청 계약이 깨진다.
 */
package kr.co.alpharking.dto.parking;

public record ParkingAssignRequest(Long parkingSpaceId) {}
