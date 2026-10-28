/** 파일 안내
 * 용도: U 사용자 HTTP·WebSocket에 반환하는 불변 구획 스냅샷.
 * 사용처·연결: ParkingSpaceQueryRepository → 서비스/Controller와 ParkingWebSocketHandler.Snapshot.
 * record의 값 비교를 통해 U 소켓이 변경 여부를 판정한다. 메모·차량번호는 포함하지 않는다.
 */
package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;

/** 로그인한 사용자에게 제공할 주차현황. 차량번호와 관리자 메모는 포함하지 않는다. */
public record ParkingSpacePublicRow(
        // 예약과 도면 선택이 사용하는 실제 PARKING_SPACE PK.
        Long parkingSpaceId,
        // 화면 층 선택에 사용하는 숫자와 표시명.
        Integer floorNo,
        String floorName,
        // 구역 코드와 구획 번호. spaceCode를 구성하는 원본 값이다.
        String zoneCode,
        String spaceNumber,
        // 전용 구획 종류. 점유 상태와 별개다.
        String spaceTypeCode,
        // 유효 예약이 반영될 수 있는 사용자 표시 상태. DB 원본을 수정한 결과는 아니다.
        String spaceStatusCode,
        // AI와 공유하는 640×480 기준의 DB 좌표와 크기. 화면 확대 배율은 프론트가 적용한다.
        BigDecimal xPosition,
        BigDecimal yPosition,
        BigDecimal width,
        BigDecimal height,
        // 층F-구역번호 형식의 구획 코드. 예: 1F-A01.
        String spaceCode,
        // DB 구획 수정 시각. 계산된 예약 표시의 변경 시각을 뜻하지는 않는다.
        String updatedAt) {}
