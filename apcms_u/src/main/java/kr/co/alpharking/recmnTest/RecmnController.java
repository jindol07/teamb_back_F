package kr.co.alpharking.recmnTest;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

import com.fasterxml.jackson.core.JsonProcessingException;

import jakarta.validation.Valid;
import kr.co.alpharking.security.Office;

@RestController
@RequestMapping("/api/recmn")
public class RecmnController {

    private final RecmnService recmnService;
    private final RestClient restClient;

    public RecmnController(
            RecmnService recmnService,
            @Value("${app.ai.recmn.base-url}") String fastApiUrl) {

        this.recmnService = recmnService;

        // SimpleClientHttpRequestFactory로 FastAPI에 요청을 보내야 정상 전달
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000);
        factory.setReadTimeout(30000);

        this.restClient = RestClient.builder()
                .baseUrl(fastApiUrl)
                .requestFactory(factory)
                .requestInterceptor((request, body, execution) -> {
                    // System.out.println("FastAPI 요청 URL: " + request.getURI());
                    return execution.execute(request, body);
                })
                .build();
    }

    /**
     * 예약 목록 및 AI 예측 기본 조회 예제
     */
    @GetMapping
    public Map<String, Object> getReservations(Authentication authentication) throws JsonProcessingException {
        // JWT 필터의 principal에 들어 있는 Office 객체에서 인증 ID 조회
        Long officeId = ((Office) authentication.getPrincipal()).getOffice_id();

        // 사용자 과거 주차 이력 조회
        List<PrkPastHisRes> historyData = recmnService.getPrkPastHisById(officeId);
        
        // 예약 화면에서 받을 값으로 추후 변경 예정
        String reservationAt = "2026-10-16T09:00:00";

        // FastAPI 요청 JSON 구성
        List<Map<String, String>> dataPrc = historyData.stream()
                .map(item -> Map.of(
                        "entry_at", item.getUsageDate().replace(" ", "T"),
                        "zone_code", item.getTargetZone()
                ))
                .toList();

        Map<String, Object> requestData = Map.of(
                "office_id", officeId,
                "reservation_at", reservationAt,
                "history", dataPrc
        );

        // FastAPI 호출
        Map<String, Object> aiResponse = restClient.post()
                .uri("/api/recmn/predict")
                .body(requestData)
                .retrieve()
                .body(new ParameterizedTypeReference<Map<String, Object>>() {});

        return aiResponse;
    }

    /**
     * 선택한 기간에 이용 가능한 주차 공간 추천
     */
    @PostMapping("/recommend")
    public ParkingRecommendationResponse recommendParking(
            Authentication authentication,
            @Valid @RequestBody ParkingRecommendationRequest request) {

        // JWT 인증 principal에서 현재 사용자 ID 조회
        Long officeId = ((Office) authentication.getPrincipal()).getOffice_id();

        List<PrkPastHisRes> historyData = recmnService.getPrkPastHisById(officeId);
        List<Map<String, String>> dataPrc = historyData.stream()
                .map(item -> Map.of(
                        "entry_at", item.getUsageDate().replace(" ", "T"),
                        "zone_code", item.getTargetZone()
                ))
                .toList();

        String reservationAt = request.getStartDate().atTime(9, 0).toString();
        Map<String, Object> requestData = Map.of(
                "office_id", officeId,
                "reservation_at", reservationAt,
                "history", dataPrc
        );

        Map<String, Object> aiResponse = restClient.post()
                .uri("/api/recmn/predict")
                .body(requestData)
                .retrieve()
                .body(new ParameterizedTypeReference<Map<String, Object>>() {});
        
        System.out.println("===== AI 추천 결과 =====");
        System.out.println("officeId = " + officeId);
        System.out.println("AI 응답 = " + aiResponse);

        Object rawRecommendations = aiResponse == null ? null : aiResponse.get("recommendations");
        if (!(rawRecommendations instanceof List<?> recommendationRows)) {
            throw new IllegalStateException("AI 추천 응답에 구역 순위가 없습니다.");
        }

        List<String> recommendedZones = new ArrayList<>();
        Map<String, Double> zoneScores = new java.util.LinkedHashMap<>();
        
        for (Object recommendationRow : recommendationRows) {
            if (recommendationRow instanceof Map<?, ?> recommendation) {
                Object zoneCode = recommendation.get("zone_code");
                if (zoneCode instanceof String) {
                    recommendedZones.add((String) zoneCode);
                    Object score = recommendation.get("score");
                    if (score instanceof Number) {
                        zoneScores.put((String) zoneCode, ((Number) score).doubleValue());
                    }
                }
            }
        }

        if (historyData.isEmpty()) {
            return recmnService.recommendRandomParking(officeId, request, zoneScores);
        }

        return recmnService.recommendParking(officeId, request, recommendedZones);
    }
}