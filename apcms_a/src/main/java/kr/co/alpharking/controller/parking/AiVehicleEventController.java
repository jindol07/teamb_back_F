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
    private void requireKey(String provided) {
        if (key.isBlank()) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "AI API 키 미설정");
        if (provided == null || !MessageDigest.isEqual(key.getBytes(StandardCharsets.UTF_8),
                 provided.getBytes(StandardCharsets.UTF_8)))
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "AI API 키 불일치");
    }
    @PostMapping("/vehicle-events")
    public AiVehicleEventResponse passage(@RequestHeader(value="X-AI-API-Key", required=false) String token,
                                            @RequestBody AiVehicleEventRequest request) {
        requireKey(token);
        return service.receive(request,"VEHICLE_PASSAGE");
    }
    @PostMapping("/space-match-events")
    public AiVehicleEventResponse match(@RequestHeader(value="X-AI-API-Key", required=false) String token,
                                          @RequestBody AiVehicleEventRequest request) {
        requireKey(token);
        return service.receive(request,"VEHICLE_SPACE_MATCH");
    }
}
