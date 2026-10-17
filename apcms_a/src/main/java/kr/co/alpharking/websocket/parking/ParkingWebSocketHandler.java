package kr.co.alpharking.websocket.parking;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.ConcurrentWebSocketSessionDecorator;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import kr.co.alpharking.dao.parking.ParkingSpaceDao;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;
import tools.jackson.databind.ObjectMapper;

/** 공개 현황 전송 전용. 차량번호·관리자 메모와 DB 변경 요청은 처리하지 않는다. */
@Component
public class ParkingWebSocketHandler extends TextWebSocketHandler {
    private static final Logger log = LoggerFactory.getLogger(ParkingWebSocketHandler.class);
    private final Map<String, WebSocketSession> sessions = new ConcurrentHashMap<>();
    private final ParkingSpaceDao dao;
    private final ObjectMapper objectMapper;
    private final TransactionTemplate readTransaction;
    // 저장 요청 스레드가 전송/추가 DB 연결을 기다리지 않도록 순서대로 전송한다.
    private final ExecutorService broadcasts = Executors.newSingleThreadExecutor(
            Thread.ofPlatform().name("parking-space-broadcast").daemon(true).factory());

    public ParkingWebSocketHandler(ParkingSpaceDao dao, ObjectMapper objectMapper,
                                   PlatformTransactionManager transactionManager) {
        this.dao = dao;
        this.objectMapper = objectMapper;
        this.readTransaction = new TransactionTemplate(transactionManager);
        this.readTransaction.setReadOnly(true);
        // AFTER_COMMIT에 남아 있는 MyBatis 세션/캐시를 재사용하지 않는다.
        this.readTransaction.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessions.put(session.getId(), new ConcurrentWebSocketSessionDecorator(session, 5000, 262144));
        // 브라우저가 연결 직후 GET으로 초기 목록을 조회한다.
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        if ("PING".equals(message.getPayload())) {
            WebSocketSession target = sessions.get(session.getId());
            if (target != null) send(target, new TextMessage("PONG"));
        } else {
            // 이 연결에서는 상태 변경을 요청할 수 없다.
            disconnect(session, CloseStatus.POLICY_VIOLATION);
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        sessions.remove(session.getId());
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.warn("주차현황 웹소켓 연결 오류: {}", session.getId(), exception);
        disconnect(session, CloseStatus.SERVER_ERROR);
    }

    public void broadcastLatest() {
        try {
            broadcasts.execute(this::sendLatest);
        } catch (RejectedExecutionException exception) {
            log.warn("서버 종료 중 주차현황 전송을 예약하지 못했습니다.", exception);
        }
    }

    /** 커밋 스레드와 분리하고 조회부터 전송까지 순서대로 처리한다. */
    private void sendLatest() {
        if (sessions.isEmpty()) return;
        try {
            List<ParkingSpacePublicRow> spaces = readTransaction.execute(status -> dao.findAllPublic());
            TextMessage message = new TextMessage(objectMapper.writeValueAsString(
                    new Snapshot("PARKING_SPACES_SNAPSHOT", spaces)));
            for (WebSocketSession session : sessions.values()) send(session, message);
        } catch (Exception exception) {
            log.error("커밋 후 주차현황 전송 실패. 클라이언트가 재연결하여 다시 조회합니다.", exception);
            for (WebSocketSession session : sessions.values()) disconnect(session, CloseStatus.SERVER_ERROR);
        }
    }

    private void send(WebSocketSession session, TextMessage message) {
        try {
            if (!session.isOpen()) {
                sessions.remove(session.getId());
                return;
            }
            session.sendMessage(message);
        } catch (Exception exception) {
            log.warn("주차현황 웹소켓 전송 실패: {}", session.getId(), exception);
            disconnect(session, CloseStatus.SERVER_ERROR);
        }
    }

    private void disconnect(WebSocketSession session, CloseStatus status) {
        sessions.remove(session.getId());
        try {
            session.close(status);
        } catch (IOException exception) {
            log.debug("주차현황 웹소켓 종료 실패: {}", session.getId(), exception);
        }
    }

    @PreDestroy
    public void shutdown() {
        broadcasts.shutdownNow();
        for (WebSocketSession session : sessions.values()) disconnect(session, CloseStatus.GOING_AWAY);
    }

    public record Snapshot(String type, List<ParkingSpacePublicRow> spaces) {}
}
