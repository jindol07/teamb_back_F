/** [1023_1010] 파일 안내
 * 용도: U 사용자 HTTP·WebSocket에 반환하는 불변 구획 스냅샷.
 * 사용처·연결: ParkingSpaceQueryRepository → 서비스/Controller와 ParkingWebSocketHandler.Snapshot.
 * record의 값 비교를 통해 U 소켓이 변경 여부를 판정한다. 메모·차량번호는 포함하지 않는다.
 */
package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;

/** 로그인한 사용자에게 제공할 주차현황. 차량번호와 관리자 메모는 포함하지 않는다. */
public record ParkingSpacePublicRow(
        Long parkingSpaceId,
        Integer floorNo,
        String floorName,
        String zoneCode,
        String spaceNumber,
        String spaceTypeCode,
        String spaceStatusCode,
        BigDecimal xPosition,
        BigDecimal yPosition,
        BigDecimal width,
        BigDecimal height,
        String spaceCode,
        String updatedAt) {}
