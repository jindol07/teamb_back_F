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

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void afterCommit(ParkingSpaceChangedEvent event) {
        // 롤백된 변경은 전송하지 않으며, 전송 실패를 저장 실패로 반환하지 않는다.
        handler.broadcastLatest();
    }
}
