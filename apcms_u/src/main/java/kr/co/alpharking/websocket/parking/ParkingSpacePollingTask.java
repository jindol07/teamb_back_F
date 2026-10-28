/** 파일 안내
 * 용도: 접속자가 있는 U 인스턴스의 공통 DB 현황 확인 작업.
 * 사용처·연결: Spring 생명주기 → ParkingSpaceQueryService → ParkingWebSocketHandler.broadcastIfChanged.
 * 인증된 연결이 있을 때만 조회한다. 기본 2초이며 이전 작업 종료 후 간격을 두어 조회 중첩을 피한다.
 */
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

    // 설정된 조회 주기가 500ms 미만이면 시작하지 않는다. 기본 주기는 2000ms다.
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
    // 서버 인스턴스당 공통 스케줄러다. 연결마다 타이머를 만드는 구조가 아니다.
    public void start() {
        // 이전 작업 완료 후 간격을 두어 DB 조회가 겹치지 않게 한다.
        scheduler.scheduleWithFixedDelay(this::poll, 0, intervalMillis, TimeUnit.MILLISECONDS);
    }

    // 인증된 접속자가 있을 때만 조회한다. 결과 변경·새 연결 전송 판단은 handler에 위임한다.
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
    // 서버 종료 시 스케줄러를 중지하여 조회 작업을 남기지 않는다.
    public void shutdown() {
        scheduler.shutdownNow();
    }
}
