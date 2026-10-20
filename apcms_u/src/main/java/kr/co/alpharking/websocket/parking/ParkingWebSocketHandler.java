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
    private Snapshot latest;
    private long revision;

    public ParkingWebSocketHandler(ObjectMapper objectMapper, ParkingWebSocketAuthService authService) {
        this.objectMapper = objectMapper;
        this.authService = authService;
    }

    private void onAuthenticated() {
        // 새 인증 연결에는 다음 공통 DB 조회가 성공한 최신 결과를 보낸다.
    }

    public boolean hasConnections() {
        // 미인증 연결은 DB 주기 조회를 시작하는 접속자 수에 포함하지 않는다.
        return clients.values().stream().anyMatch(this::isAuthenticated);
    }

    public synchronized void broadcastIfChanged(List<ParkingSpacePublicRow> spaces) {
        Snapshot next = new Snapshot("PARKING_SPACES_SNAPSHOT", List.copyOf(spaces));
        if (!next.equals(latest)) {
            latest = next;
            revision += 1;
        }
        List<Client> targets = clients.values().stream()
                .filter(this::isAuthenticated).filter(client -> client.sentRevision != revision).toList();
        if (targets.isEmpty()) return;
        TextMessage message = new TextMessage(objectMapper.writeValueAsString(latest));
        for (Client client : targets) {
            if (send(client, message)) client.sentRevision = revision;
        }
    }

    public void closeForRefreshFailure() {
        for (Client client : clients.values()) {
            if (client.identity != null) disconnect(client.session, CloseStatus.SERVER_ERROR);
        }
    }

    @PreDestroy
    public void shutdown() {
        authChecks.shutdownNow();
        for (Client client : clients.values()) disconnect(client.session, CloseStatus.GOING_AWAY);
    }

    @PostConstruct
    public void startAuthChecks() {
        authChecks.scheduleWithFixedDelay(this::checkConnections, 1, 1, TimeUnit.SECONDS);
    }

    @Override
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
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        clients.remove(session.getId());
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) {
        log.warn("주차현황 웹소켓 연결 오류: {}", session.getId());
        disconnect(session, CloseStatus.SERVER_ERROR);
    }

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

    private void disconnect(WebSocketSession session, CloseStatus status) {
        clients.remove(session.getId());
        try {
            session.close(status);
        } catch (IOException exception) {
            log.debug("주차현황 웹소켓 종료 실패: {}", session.getId());
        }
    }

    private static class Client {
        private final WebSocketSession session;
        private final long connectedAt = System.nanoTime();
        private volatile ParkingWebSocketAuthService.Identity identity;
        private volatile long sentRevision = -1;

        private Client(WebSocketSession session) { this.session = session; }
    }

    public record AuthRequest(String type, String token) {}
    public record Snapshot(String type, List<ParkingSpacePublicRow> spaces) {}
}
