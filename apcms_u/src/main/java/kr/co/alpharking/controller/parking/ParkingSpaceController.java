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

    @GetMapping
    public List<ParkingSpacePublicRow> spaces() {
        return service.findAll();
    }
}
