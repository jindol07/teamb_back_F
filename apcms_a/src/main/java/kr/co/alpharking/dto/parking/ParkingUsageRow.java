/** 파일 안내
 * 용도: 입출차·구획 연결 조회 결과.
 * 사용처·연결: parking-usage.xml·vehicle.xml → 주차 서비스/Controller, VehicleDTO의 이용 기록 목록.
 * 미등록 차량 vehicleId·미배정 parkingSpaceId·미출차 exitAt은 null일 수 있다. 최근 기록과 active 집계에 함께 사용된다.
 */
package kr.co.alpharking.dto.parking;

import lombok.Data;
import org.apache.ibatis.type.Alias;

@Data
@Alias("ParkingUsageRow")
public class ParkingUsageRow {
    // 이용 기록 PK. 기존 미출차 기록 선택·출차·배정의 대상이다.
    private Long parkingUsageId;
    // AI 구획 연결의 버전. 이 값을 조회하지 않는 SQL 결과에서는 null일 수 있다.
    private Long linkVersion;
    // 등록 차량 PK. 미등록 방문 차량은 null일 수 있다.
    private Long vehicleId;
    // 번호판 문자열. 관리자 전용 조회에서는 연결된 기존 기록을 기준으로 제공한다.
    private String vehicleNumber;
    // PARKING_SPACE의 실제 숫자 PK. 도면 문자열 코드와 구분한다.
    private Long parkingSpaceId;
    // 이용 기록에 연결된 예약 PK. 수동 배정 또는 예약 미연결이면 null일 수 있다.
    private Long parkingReservationId;
    // AI와 화면이 공유하는 구획 코드. 예: 1F-A01.
    private String spaceCode;
    // 입차 감지 또는 처리 시각 문자열.
    private String entryAt;
    // 출차 시각 문자열. 기존 미출차 기록은 null이다.
    private String exitAt;
    // 등록 차량 NORMAL 또는 방문 차량 VISITOR 등의 이용 유형.
    private String parkingTypeCode;
}
