package kr.co.alpharking.controller.vehicle;

import java.util.List;
//import org.springframework.http.MediaType;

import kr.co.alpharking.dto.vehicle.VehicleDTO;
import kr.co.alpharking.service.vehicle.VehiceService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
//import org.springframework.web.multipart.MultipartFile;



@RestController
@RequestMapping("/api/vehicle")
public class VehicleController {

    private final VehiceService vehiceService;

    public VehicleController(VehiceService vehiceService) {
        this.vehiceService = vehiceService;
    }

    @PostMapping
    public ResponseEntity<Void> addVehicle(@RequestBody VehicleDTO vehicle) {
    	// Spring Boot 콘솔로 등록한 차량번호 확인용 => 이런식으로 출력됨 => === addVehicle 실행됨: 345다 6789 ===
    	System.out.println("=== addVehicle 실행됨: " + vehicle.getVehiclenumber() + " ==="); 
        vehiceService.addVehicle(vehicle);
        return ResponseEntity.ok().build();
    }

    @GetMapping
    public ResponseEntity<List<VehicleDTO>> getVehicleList() {
        List<VehicleDTO> list = vehiceService.getVehicleList();
        return ResponseEntity.ok(list);
    }

    @PutMapping("/{vehicleId}")
    public ResponseEntity<Void> updateVehicle(@PathVariable("vehicleId") Long vehicleId, @RequestBody VehicleDTO vehicle) {
        vehicle.setVehicleid(vehicleId);
        vehiceService.updateVehicle(vehicle);
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/{vehicleId}")
    public ResponseEntity<Void> deleteVehicle(@PathVariable("vehicleId") Long vehicleId) {
        vehiceService.deleteVehicle(vehicleId);
        return ResponseEntity.ok().build();
    }
    
//    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
//    	public ResponseEntity<?> uploadVehicles(
//    	        @RequestParam("file") MultipartFile file) {
//    	    // 1. 파일 확장자 및 크기 검증
//    	    // 2. XLSX / XLS / CSV 파싱
//    	    // 3. 차량 데이터 검증 및 중복 검사
//    	    // 4. Service를 통해 vehicle 테이블에 저장
//    	    // 5. 성공·실패 건수 반환
//    	    return ResponseEntity.ok().build();
//    	} => 추후 구현 예정
}