package kr.co.alpharking.websocket.parking;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import kr.co.alpharking.service.parking.ParkingSpaceQueryService;

/** Redis 없이 동작하는 U 인스턴스 공통 변경 확인 작업. */
@Component
public class ParkingSpacePollingTask {
    private static final Logger log = LoggerFactory.getLogger(ParkingSpacePollingTask.class);
    private final ParkingSpaceQueryService service;
    private final ParkingWebSocketHandler handler;
    private final long intervalMillis;
    private final ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor(
            Thread.ofPlatform().name("user-parking-poll").daemon(true).factory());

    public ParkingSpacePollingTask(ParkingSpaceQueryService service, ParkingWebSocketHandler handler,
            @Value("${parking.websocket.poll-interval-ms:2000}") long intervalMillis) {
        if (intervalMillis < 500) {
            throw new IllegalArgumentException("주차현황 조회 간격은 500ms 이상이어야 합니다.");
        }
        this.service = service;
        this.handler = handler;
        this.intervalMillis = intervalMillis;
    }

    @PostConstruct
    public void start() {
        // 이전 작업 완료 후 간격을 두어 DB 조회가 겹치지 않게 한다.
        scheduler.scheduleWithFixedDelay(this::poll, 0, intervalMillis, TimeUnit.MILLISECONDS);
    }

    public void poll() {
        if (!handler.hasConnections()) return;
        try {
            handler.broadcastIfChanged(service.findAll());
        } catch (Exception exception) {
            log.error("사용자 주차현황 공통 조회 실패. 연결을 종료하여 재조회를 유도합니다.", exception);
            handler.closeForRefreshFailure();
        }
    }

    @PreDestroy
    public void shutdown() {
        scheduler.shutdownNow();
    }
}
