package kr.co.alpharking.controller.vehiclehistory;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.vehiclehistory.VehiclehistoryDto;
import kr.co.alpharking.service.vehiclehistory.VehiclehistoryService;

@RestController
@RequestMapping("/api/vehiclehistory")
public class VehiclehistoryController {

    private final VehiclehistoryService vehiclehistoryService;

    public VehiclehistoryController(VehiclehistoryService vehiclehistoryService) {
        this.vehiclehistoryService = vehiclehistoryService;
    }

    @GetMapping
    public ResponseEntity<List<VehiclehistoryDto>> getVehicleHistoryList() {
        return ResponseEntity.ok(vehiclehistoryService.getVehicleHistoryList());
    }
}
