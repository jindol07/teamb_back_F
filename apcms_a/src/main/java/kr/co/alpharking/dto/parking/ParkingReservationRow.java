/** [1023_1010] 파일 안내
 * 용도: 관리자 예약 읽기 전용 조회 결과.
 * 사용처·연결: parking-space.xml → ParkingSpaceDao → ParkingSpaceService/Controller → 관리자 예약 카드·달력·이력.
 * 예약 생성·취소용 Entity가 아니다. 시간 문자열은 SQL에서 ISO 형태로 변환한다.
 */
package kr.co.alpharking.dto.parking;

import lombok.Data;
import org.apache.ibatis.type.Alias;

/** 관리자 전용 예약 조회 응답. 기존 예약 테이블을 읽기만 한다. */
@Data
@Alias("ParkingReservationRow")
public class ParkingReservationRow {
    // [1023_1010] 예약 기록 PK. 구획 PK와 구분한다.
    private Long parkingReservationId;
    // [1023_1010] PARKING_SPACE의 실제 숫자 PK. 도면 문자열 코드와 구분한다.
    private Long parkingSpaceId;
    // [1023_1010] 번호판 문자열. 관리자 전용 조회에서는 연결된 기존 기록을 기준으로 제공한다.
    private String vehicleNumber;
    // [1023_1010] 예약 시작 시각 문자열.
    private String reservationStartAt;
    // [1023_1010] 예약 종료 시각 문자열.
    private String reservationEndAt;
    // [1023_1010] 예약 확정·취소 등 예약 기록의 상태.
    private String statusCode;
}
