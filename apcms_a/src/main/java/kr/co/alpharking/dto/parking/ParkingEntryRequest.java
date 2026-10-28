/** 파일 안내
 * 용도: 수동 입차할 차량번호 요청.
 * 사용처·연결: ParkingUsageController.entry의 POST /api/parking/usages/entry.
 * 등록 차량 판정·번호 정규화·중복 입차 검증은 ParkingUsageService가 수행한다.
 */
package kr.co.alpharking.dto.parking;

public record ParkingEntryRequest(String vehicleNumber) {}
