/** 파일 안내
 * 용도: 관리자 소켓 인증·만료·PING/PONG·공개 구획 스냅샷 전송.
 * 사용처·연결: A ParkingWebSocketConfig, ParkingSpaceBroadcastListener, 프론트 useParkingSpaceSync(admin).
 * 인증 직후·구획 변경 커밋 후 별도 읽기 트랜잭션으로 최신 목록을 조회한다. 예약 변경의 U 서버 이벤트를 직접 구독하지는 않는다.
 */
package kr.co.alpharking.websocket.parking;

import java.io.IOException;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.AuthenticationException;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.ConcurrentWebSocketSessionDecorator;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import io.jsonwebtoken.JwtException;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.RejectedExecutionException;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
import kr.co.alpharking.dao.parking.ParkingSpaceDao;

/** 첫 AUTH 메시지로 인증한 연결에만 민감 정보를 제외한 주차현황을 전송한다. */
@Component
public class ParkingWebSocketHandler extends TextWebSocketHandler {
    private static final Logger log = LoggerFactory.getLogger(ParkingWebSocketHandler.class);
    private static final CloseStatus AUTH_FAILED = new CloseStatus(4003, "Authentication required");
    private static final CloseStatus AUTH_EXPIRED = new CloseStatus(4001, "Authentication expired");
    private static final long AUTH_TIMEOUT_NANOS = TimeUnit.SECONDS.toNanos(10);
    private static final int MAX_CONNECTIONS = 512;
    private final Map<String, Client> clients = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper;
    private final ParkingWebSocketAuthService authService;
    // 인증을 보내지 않는 연결도 반드시 정리한다. JWT 원문은 세션에 저장하지 않는다.
    private final ScheduledExecutorService authChecks = Executors.newSingleThreadScheduledExecutor(
            Thread.ofPlatform().name("parking-websocket-auth").daemon(true).factory());
    private final ParkingSpaceDao dao;
    private final TransactionTemplate readTransaction;
    private final ExecutorService broadcasts = Executors.newSingleThreadExecutor(
            Thread.ofPlatform().name("parking-space-broadcast").daemon(true).factory());

    public ParkingWebSocketHandler(ParkingSpaceDao dao, ObjectMapper objectMapper,
                                   PlatformTransactionManager transactionManager,
                                   ParkingWebSocketAuthService authService) {
        this.dao = dao;
        this.objectMapper = objectMapper;
        this.authService = authService;
        this.readTransaction = new TransactionTemplate(transactionManager);
        this.readTransaction.setReadOnly(true);
        // 커밋 이벤트의 이전 트랜잭션 자원에 기대지 않고 새 읽기 트랜잭션으로 조회한다.
        this.readTransaction.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }

    // A의 인증 성공 직후 최신 공개 현황을 조회·전송하는 작업을 예약한다.
    private void onAuthenticated() {
        // 인증 성공 직후와 DB 변경 커밋 후에 최신 현황을 보낸다.
        broadcastLatest();
    }

    // 단일 전송 실행기에 작업을 예약한다. DB 저장 트랜잭션과 네트워크 전송의 실패를 분리한다.
    public void broadcastLatest() {
        try {
            broadcasts.execute(this::sendLatest);
        } catch (RejectedExecutionException exception) {
            log.warn("서버 종료 중 주차현황 전송을 예약하지 못했습니다.");
        }
    }

    // 인증 연결이 있을 때만 별도 읽기 트랜잭션으로 최신 공개 목록을 읽어 동일 메시지를 전송한다.
    private void sendLatest() {
        List<Client> targets = clients.values().stream().filter(this::isAuthenticated).toList();
        if (targets.isEmpty()) return;
        try {
            List<ParkingSpacePublicRow> spaces = readTransaction.execute(status -> dao.findAllPublic());
            TextMessage message = new TextMessage(objectMapper.writeValueAsString(
                    new Snapshot("PARKING_SPACES_SNAPSHOT", spaces)));
            for (Client client : targets) send(client, message);
        } catch (Exception exception) {
            log.error("커밋 후 주차현황 전송 실패. 재연결 후 다시 조회합니다.", exception);
            for (Client client : targets) disconnect(client.session, CloseStatus.SERVER_ERROR);
        }
    }

    @PreDestroy
    // Spring 종료 시 백그라운드 작업과 소켓을 정리한다.
    public void shutdown() {
        authChecks.shutdownNow();
        broadcasts.shutdownNow();
        for (Client client : clients.values()) disconnect(client.session, CloseStatus.GOING_AWAY);
    }

    @PostConstruct
    // 미인증 대기·만료 토큰 확인은 PING 수신 여부와 별개로 1초마다 수행한다.
    public void startAuthChecks() {
        authChecks.scheduleWithFixedDelay(this::checkConnections, 1, 1, TimeUnit.SECONDS);
    }

    @Override
    // 연결 수 제한과 전송 동시성 장식을 적용한다. 접속만으로는 인증 완료가 아니다.
    public void afterConnectionEstablished(WebSocketSession session) {
        session.setTextMessageSizeLimit(16384);
        boolean accepted;
        synchronized (clients) {
            accepted = clients.size() < MAX_CONNECTIONS;
            if (accepted) clients.put(session.getId(), new Client(
                    new ConcurrentWebSocketSessionDecorator(session, 5000, 262144)));
        }
        if (!accepted) disconnect(session, new CloseStatus(1013, "Connection limit"));
        // 이 시점은 미인증이다. AUTH_OK 이후에만 현황 전송 대상으로 등록한다.
    }

    @Override
    // 인증 전에는 AUTH만 처리하고 인증 후에는 PING에 PONG으로 응답한다. 나머지 메시지는 정책 위반으로 종료한다.
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        Client client = clients.get(session.getId());
        if (client == null) return;
        synchronized (client) {
            if (client.identity == null) {
                authenticate(client, message);
            } else if (isAuthenticated(client)) {
                if ("PING".equals(message.getPayload())) send(client, new TextMessage("PONG"));
                else disconnect(client.session, CloseStatus.POLICY_VIOLATION);
            }
        }
    }

    // 10초 안의 AUTH를 검증한다. AUTH_OK 전송 후 identity를 공개해 현황이 인증 응답보다 앞서지 않게 한다.
    private void authenticate(Client client, TextMessage message) {
        try {
            if (System.nanoTime() - client.connectedAt >= AUTH_TIMEOUT_NANOS) {
                disconnect(client.session, AUTH_FAILED);
                return;
            }
            AuthRequest request = objectMapper.readValue(message.getPayload(), AuthRequest.class);
            if (request == null || !"AUTH".equals(request.type())) {
                disconnect(client.session, AUTH_FAILED);
                return;
            }
            ParkingWebSocketAuthService.Identity identity = authService.authenticate(request.token());
            if (!client.session.isOpen() || clients.get(client.session.getId()) != client) return;
            if (System.nanoTime() - client.connectedAt >= AUTH_TIMEOUT_NANOS) {
                disconnect(client.session, AUTH_FAILED);
                return;
            }
            if (!identity.expiresAt().isAfter(Instant.now())) {
                disconnect(client.session, AUTH_EXPIRED);
                return;
            }
            // AUTH_OK 전송이 끝난 뒤 identity를 공개하여 현황 메시지가 앞서 전송되지 않게 한다.
            client.session.sendMessage(new TextMessage("{\"type\":\"AUTH_OK\"}"));
            client.identity = identity;
            onAuthenticated();
        } catch (JwtException | AuthenticationException | IllegalArgumentException | JacksonException exception) {
            disconnect(client.session, AUTH_FAILED);
        } catch (Exception exception) {
            // 메시지/JWT 원문이나 예외 메시지는 로그에 남기지 않는다.
            log.warn("주차 소켓 인증 처리 실패: session={}, error={}",
                    client.session.getId(), exception.getClass().getSimpleName());
            disconnect(client.session, CloseStatus.SERVER_ERROR);
        }
    }

    // 소켓 생존·등록된 세션·JWT 만료를 확인한다. 만료 연결은 종료한다.
    private boolean isAuthenticated(Client client) {
        if (!client.session.isOpen() || clients.get(client.session.getId()) != client) {
            clients.remove(client.session.getId(), client);
            return false;
        }
        ParkingWebSocketAuthService.Identity identity = client.identity;
        if (identity == null) return false;
        if (!identity.expiresAt().isAfter(Instant.now())) {
            disconnect(client.session, AUTH_EXPIRED);
            return false;
        }
        return true;
    }

    // 닫힌 연결·시간 초과된 미인증 연결·만료된 인증 연결을 정리한다.
    private void checkConnections() {
        for (Client client : clients.values()) {
            if (!client.session.isOpen()) clients.remove(client.session.getId(), client);
            else if (client.identity == null) {
                if (System.nanoTime() - client.connectedAt >= AUTH_TIMEOUT_NANOS) {
                    disconnect(client.session, AUTH_FAILED);
                }
            } else isAuthenticated(client);
        }
    }

    @Override
    // 정상 또는 원격 연결 종료 후 세션 참조를 제거한다.
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        clients.remove(session.getId());
    }

    @Override
    // 전송 오류 세션을 닫는다. 프론트는 일반 연결 장애 시 HTTP 대체 조회·재연결을 수행한다.
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.warn("주차현황 웹소켓 연결 오류: {}", session.getId());
        disconnect(session, CloseStatus.SERVER_ERROR);
    }

    // 전송 직전 인증 상태를 확인한다. 실패한 세션은 유지하지 않고 정리한다.
    private boolean send(Client client, TextMessage message) {
        if (!isAuthenticated(client)) return false;
        try {
            client.session.sendMessage(message);
            return true;
        } catch (Exception exception) {
            log.warn("주차현황 웹소켓 전송 실패: {}", client.session.getId());
            disconnect(client.session, CloseStatus.SERVER_ERROR);
            return false;
        }
    }

    // 클라이언트 목록에서 제거하고 종료 코드를 보내 소켓을 닫는다.
    private void disconnect(WebSocketSession session, CloseStatus status) {
        clients.remove(session.getId());
        try {
            session.close(status);
        } catch (IOException exception) {
            log.debug("주차현황 웹소켓 종료 실패: {}", session.getId());
        }
    }

    // 연결별 자원·인증 결과를 보관한다. 같은 연결의 인증/메시지 처리는 동기화된다.
    private static class Client {
        private final WebSocketSession session;
        private final long connectedAt = System.nanoTime();
        private volatile ParkingWebSocketAuthService.Identity identity;

        private Client(WebSocketSession session) { this.session = session; }
    }

    // 첫 수신 JSON 계약: type=AUTH와 JWT token. URL 쿼리로 인증하지 않는다.
    public record AuthRequest(String type, String token) {}
    // 프론트가 처리하는 메시지 계약: PARKING_SPACES_SNAPSHOT과 공개 구획 목록.
    public record Snapshot(String type, List<ParkingSpacePublicRow> spaces) {}
}
