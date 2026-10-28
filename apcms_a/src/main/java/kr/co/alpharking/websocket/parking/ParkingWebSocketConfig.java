/** 파일 안내
 * 용도: A의 주차 현황 WebSocket 경로·허용 Origin 등록.
 * 사용처·연결: Spring 설정 검색 → /ws/parking/spaces → A ParkingWebSocketHandler.
 * 실제 URL에는 A context-path가 붙는다. Origin 허용은 JWT 인증을 대신하지 않는다.
 */
package kr.co.alpharking.websocket.parking;

import java.util.Arrays;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
public class ParkingWebSocketConfig implements WebSocketConfigurer {
    private final ParkingWebSocketHandler handler;
    private final String[] allowedOriginPatterns;

    public ParkingWebSocketConfig(ParkingWebSocketHandler handler,
            @Value("${parking.websocket.allowed-origin-patterns:http://localhost:3000,http://127.0.0.1:3000,http://192.168.*:3000}")
            String allowedOriginPatterns) {
        this.handler = handler;
        this.allowedOriginPatterns = Arrays.stream(allowedOriginPatterns.split(","))
                .map(String::trim).filter(value -> !value.isEmpty()).toArray(String[]::new);
    }

    @Override
    // Spring이 실제 소켓 경로에 handler를 등록한다. 이 등록과 별개로 첫 메시지 JWT 검증을 통과해야 한다.
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        // context-path를 포함한 실제 주소: /alpharking/admin/ws/parking/spaces
        registry.addHandler(handler, "/ws/parking/spaces")
                .setAllowedOriginPatterns(allowedOriginPatterns);
    }
}
