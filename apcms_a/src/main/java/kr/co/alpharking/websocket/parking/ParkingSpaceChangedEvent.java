/** [1023_1010] 파일 안내
 * 용도: 구획 변경 커밋 후 공개 현황 전송을 요청하는 도메인 이벤트.
 * 사용처·연결: ParkingSpaceService·AiOccupancyService 발행 → ParkingSpaceBroadcastListener.
 * 행 데이터나 인증정보를 담지 않는다. 리스너가 커밋 후 DB 현황을 다시 읽는다.
 */
package kr.co.alpharking.websocket.parking;

/** 변경 트랜잭션이 커밋된 뒤 공개 주차구획 목록을 다시 전송하기 위한 알림. */
public record ParkingSpaceChangedEvent() {}
