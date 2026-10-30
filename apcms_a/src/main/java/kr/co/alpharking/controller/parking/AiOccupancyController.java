/** 파일 안내
 * 용도: AI 점유 이벤트를 받는 내부 HTTP 진입점.
 * 사용처·연결: 외부 AI 송신기 → POST /api/parking/ai/occupancy-events → AiOccupancyService.
 * X-AI-API-Key를 환경설정 AI_OCCUPANCY_API_KEY와 비교한다. 관리자 JWT 보정 API와 다른 계약이다.
 */
package kr.co.alpharking.controller.parking;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.AiOccupancyRequest;
import kr.co.alpharking.dto.parking.AiOccupancyResponse;
import kr.co.alpharking.service.parking.AiOccupancyService;

/** AI 전용 내부 수신 API. 관리자 세션과 분리하며 공유 비밀키 검증을 강제. */
@RestController
@RequestMapping("/api/parking/ai")
public class AiOccupancyController {
    private final AiOccupancyService service;
    private final String apiKey;

    public AiOccupancyController(AiOccupancyService service,
                                 @Value("${AI_OCCUPANCY_API_KEY:}") String apiKey) {
        this.service = service;
        this.apiKey = apiKey;
    }

    // 공유 API 키 검증을 통과한 점유 이벤트만 서비스로 전달한다.
    @PostMapping("/occupancy-events")
    public AiOccupancyResponse accept(@RequestHeader(value="X-AI-API-Key", required=false) String supplied,
                                       @RequestBody AiOccupancyRequest request) {
        if (apiKey.isBlank()) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "AI API 키 미설정");
        // 문자열 일반 비교 대신 MessageDigest 비교를 사용한다. 실제 키 값은 주석·로그에 기록하지 않는다.
        if (supplied == null || !MessageDigest.isEqual(
            apiKey.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8))) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "AI API 키가 일치하지 않습니다.");
        }
        return service.receive(request);
    }
}


//시연용