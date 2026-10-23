package kr.co.alpharking.recmnTest;

import java.util.List;
import java.util.Map;
import java.util.ArrayList;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;

import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import com.fasterxml.jackson.core.JsonProcessingException;

import jakarta.validation.Valid;
import kr.co.alpharking.security.Office;

//import tools.jackson.databind.ObjectMapper;

//import org.springframework.http.MediaType;

@RestController
@RequestMapping("/api/recmn")
public class RecmnController {

	private RecmnService recmnService;

	private RestClient restClient;

//	@Autowired
//	private ObjectMapper objectMapper;

	public RecmnController(
            RecmnService recmnService,
            @Value("${app.ai.recmn.base-url}") String fastApiUrl) {

        this.recmnService = recmnService;
        //SimpleClientHttpRequestFactory로 fastapi에 요청을 보내야 정상 전달
        SimpleClientHttpRequestFactory factory =
                new SimpleClientHttpRequestFactory();

        factory.setConnectTimeout(5000);
        factory.setReadTimeout(30000);

        this.restClient = RestClient.builder()
                .baseUrl(fastApiUrl)
                .requestFactory(factory)
                .requestInterceptor((request, body, execution) -> {

                    //System.out.println("FastAPI 요청 URL: " + request.getURI());
                    //System.out.println("FastAPI 요청 Method: " + request.getMethod());
                    //System.out.println("FastAPI 요청 Headers: " + request.getHeaders());
                    //System.out.println("FastAPI 요청 Body 크기: " + body.length);

                    return execution.execute(request, body);
                })
                .build();
    }

//	@GetMapping("/{officeId}")
//    public List<PrkPastHisRes> getPrkPastHisById(
//            @PathVariable("officeId") Long officeId) {
//
//        return recmnService.getPrkPastHisById(officeId);
//    }



//1019: 리액트 <ㅡ> 부트 동작 예제
//React: userApi.get('/api/reservation') -> JWT Authorization 헤더 전달
//JwtTokenFilter: account_id = 1 -> RecmnController: officeId = 1
//recmnService -> recmnRepository -> DB: WHERE office_id = 1
	@GetMapping
    public Map<String, Object> getReservations(Authentication authentication) throws JsonProcessingException {
		//인증ID
        // JWT 필터의 principal에 들어 있는 Office 객체에서 인증 ID 조회
        Long officeId = ((Office) authentication.getPrincipal()).getOffice_id();
        //사용자 과거 주차 이력(A, B, C 구역)
        List<PrkPastHisRes> historyData = recmnService.getPrkPastHisById(officeId);
        //예약 화면에서 받을 값으로 추후 변경!
        String reservationAt = "2026-10-16T09:00:00";
        //FastAPI 요청 JSON 구성
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

     // 실제 전송할 JSON 확인
        //String jsonBody = objectMapper.writeValueAsString(requestData);
        //System.out.println("FastAPI 요청 JSON = " + jsonBody);

        //FastAPI 호출
        Map<String, Object> aiResponse = restClient.post()
                .uri("/api/recmn/predict")
                //FastAPI JSON 요청 처리 명시
                //.contentType(MediaType.APPLICATION_JSON)
                .body(requestData)
                .retrieve()
                .body(new ParameterizedTypeReference<Map<String, Object>>() {});


        //일단 UI 구현이 안 되어 있으므로 예약일시 하드코딩
        //아래는 리액트 코드라서 자바문법에 맞게 수정
        //const reservationAt = '2026-10-16T09:00:00';
        //aiReq == requestData라고 생각
//        const requestData = {
//                office_id: officeId,
//                reservation_at: reservationAt,
//                history: historyData
//              };
        //FastAPi 요청
//        const aiResponse = await axios.post(
//                `${FASTAPI_BASE_URL}/api/recmn/predict`,
//                requestData
//              );
        //리액트 리턴 참고로 @RestController라서 JSON데이터로 리턴이 됨
        return aiResponse;
    }

    // 선택한 기간에 이용 가능한 주차 공간 추천
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
