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

    @PostMapping("/occupancy-events")
    public AiOccupancyResponse accept(@RequestHeader(value="X-AI-API-Key", required=false) String supplied,
                                       @RequestBody AiOccupancyRequest request) {
        if (apiKey.isBlank()) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "AI API 키 미설정");
        if (supplied == null || !MessageDigest.isEqual(
            apiKey.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8))) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "AI API 키가 일치하지 않습니다.");
        }
        return service.receive(request);
    }
}
