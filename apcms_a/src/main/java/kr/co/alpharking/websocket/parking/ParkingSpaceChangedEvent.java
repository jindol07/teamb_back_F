package kr.co.alpharking.websocket.parking;

/** 변경 트랜잭션이 커밋된 뒤 공개 주차구획 목록을 다시 전송하기 위한 알림. */
public record ParkingSpaceChangedEvent() {}
