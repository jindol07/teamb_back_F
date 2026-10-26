/** [1023_1010] 파일 안내
 * 용도: 로그인 사용자 주차 현황 HTTP 조회.
 * 사용처·연결: parkingSpaceApi의 user 조회 → GET /api/parking/spaces → ParkingSpaceQueryService.
 * 접근 인증은 U SecurityConfig가 적용하며 공개 DTO에는 메모·차량번호가 없다.
 */
package kr.co.alpharking.controller.parking;

import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;
import kr.co.alpharking.service.parking.ParkingSpaceQueryService;

/** U의 기존 SecurityConfig에 따라 인증이 필요한 사용자 주차현황 조회 API. */
@RestController
@RequestMapping("/api/parking/spaces")
public class ParkingSpaceController {
    private final ParkingSpaceQueryService service;

    public ParkingSpaceController(ParkingSpaceQueryService service) {
        this.service = service;
    }

    // [1023_1010] 사용자 HTTP 조회. 인증·접근 규칙은 U의 기존 SecurityFilterChain에서 처리한다.
    @GetMapping
    public List<ParkingSpacePublicRow> spaces() {
        return service.findAll();
    }
}
