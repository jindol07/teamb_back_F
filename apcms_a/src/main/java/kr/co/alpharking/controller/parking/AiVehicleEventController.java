/** [1023_1010] 파일 안내
 * 용도: AI 입출차·차량 구획 매칭 이벤트의 HTTP 진입점.
 * 사용처·연결: 외부 AI 송신기 → vehicle-events 또는 space-match-events → AiVehicleEventService.
 * API 키를 먼저 검증하고 URL별 기대 event_type을 서비스에 전달한다.
 */
package kr.co.alpharking.controller.parking;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.AiVehicleEventRequest;
import kr.co.alpharking.dto.parking.AiVehicleEventResponse;
import kr.co.alpharking.service.parking.AiVehicleEventService;

@RestController
@RequestMapping("/api/parking/ai")
public class AiVehicleEventController {
    private final AiVehicleEventService service;
    private final String key;
    public AiVehicleEventController(AiVehicleEventService service,
        @Value("${AI_OCCUPANCY_API_KEY:}") String key) { this.service = service; this.key = key; }
    // [1023_1010] 환경 키 미설정은 503, 요청 키 누락·불일치는 401이다. 키 원문을 로그에 남기지 않는다.
    private void requireKey(String provided) {
        if (key.isBlank()) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "AI API 키 미설정");
        if (provided == null || !MessageDigest.isEqual(key.getBytes(StandardCharsets.UTF_8),
                 provided.getBytes(StandardCharsets.UTF_8)))
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "AI API 키 불일치");
    }
    // [1023_1010] 입출차 통과 이벤트는 기대 유형 VEHICLE_PASSAGE로 검증한다.
    @PostMapping("/vehicle-events")
    public AiVehicleEventResponse passage(@RequestHeader(value="X-AI-API-Key", required=false) String token,
                                            @RequestBody AiVehicleEventRequest request) {
        requireKey(token);
        return service.receive(request,"VEHICLE_PASSAGE");
    }
    // [1023_1010] 구획 매칭은 기대 유형 VEHICLE_SPACE_MATCH로 검증한다.
    @PostMapping("/space-match-events")
    public AiVehicleEventResponse match(@RequestHeader(value="X-AI-API-Key", required=false) String token,
                                          @RequestBody AiVehicleEventRequest request) {
        requireKey(token);
        return service.receive(request,"VEHICLE_SPACE_MATCH");
    }
}
