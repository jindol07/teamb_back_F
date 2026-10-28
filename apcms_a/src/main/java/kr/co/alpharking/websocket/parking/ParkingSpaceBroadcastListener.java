/** 파일 안내
 * 용도: 구획 변경 트랜잭션의 커밋 이후 전송을 연결하는 리스너.
 * 사용처·연결: ParkingSpaceChangedEvent → A ParkingWebSocketHandler.broadcastLatest.
 * AFTER_COMMIT이므로 롤백된 상태는 전송하지 않는다. 저장과 네트워크 전송 실패를 구분한다.
 */
package kr.co.alpharking.websocket.parking;

import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class ParkingSpaceBroadcastListener {
    private final ParkingWebSocketHandler handler;

    public ParkingSpaceBroadcastListener(ParkingWebSocketHandler handler) {
        this.handler = handler;
    }

    // 커밋 성공 뒤에만 호출한다. 롤백된 구획 상태를 실시간 화면에 먼저 노출하지 않는다.
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void afterCommit(ParkingSpaceChangedEvent event) {
        // 롤백된 변경은 전송하지 않으며, 전송 실패를 저장 실패로 반환하지 않는다.
        handler.broadcastLatest();
    }
}
