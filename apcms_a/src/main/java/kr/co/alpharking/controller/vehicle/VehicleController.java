package kr.co.alpharking.controller.vehicle;

import java.util.List;

import kr.co.alpharking.dto.vehicle.VehicleDTO;
import kr.co.alpharking.service.vehicle.VehiceService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;


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
}