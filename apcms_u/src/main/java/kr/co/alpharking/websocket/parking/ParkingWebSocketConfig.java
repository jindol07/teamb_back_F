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
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        // 실제 URL: /alpharking/ws/parking/spaces
        // JWT 연결 방식은 회의 후 기존 인증 설정과 맞춘다. 익명 허용은 추가하지 않는다.
        registry.addHandler(handler, "/ws/parking/spaces")
                .setAllowedOriginPatterns(allowedOriginPatterns);
    }
}
