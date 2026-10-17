package kr.co.alpharking.controller.vehicle; // 본인의 controller 패키지 경로에 맞게 수정

import kr.co.alpharking.dto.vehicle.VehicleSaveRequestDto;
import kr.co.alpharking.entity.vehicle.FavoriteVisitorVehicle;
import kr.co.alpharking.service.vehicle.FavoriteVisitorVehicleService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/vehicles")
public class FavoriteVisitorVehicleController {

    private final FavoriteVisitorVehicleService vehicleService;

    // 방문자 차량 등록 API
    @PostMapping
    public ResponseEntity<Long> registerVehicle(@RequestBody VehicleSaveRequestDto requestDto) {
        Long savedId = vehicleService.registerVehicle(
                requestDto.getOfficeId(),
                requestDto.getVehicleNumber(),
                requestDto.getAliasName()
        );
        return ResponseEntity.ok(savedId);
    }

    // 특정 오피스의 방문자 차량 목록 조회 API
    @GetMapping("/office/{officeId}")
    public ResponseEntity<List<FavoriteVisitorVehicle>> getVehiclesByOffice(@PathVariable Long officeId) {
        List<FavoriteVisitorVehicle> vehicles = vehicleService.getVehiclesByOffice(officeId);
        return ResponseEntity.ok(vehicles);
    }
}