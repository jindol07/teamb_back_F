package kr.co.alpharking.controller.vehicle;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import kr.co.alpharking.dto.vehicle.VehicleExcelUploadResultDTO;
import kr.co.alpharking.service.vehicle.VehiceService;

@RestController
@RequestMapping("/api/vehicleup")
public class VehicleExcelUploadController {

    private final VehiceService vehiceService;

    public VehicleExcelUploadController(VehiceService vehiceService) {
        this.vehiceService = vehiceService;
    }
    
    @PostMapping("/upload-excel")
    public ResponseEntity<?> uploadExcel(
            @RequestParam("file") MultipartFile file) {

        try {
        	VehicleExcelUploadResultDTO result =
                    vehiceService.uploadVehiclesExcel(file);

            return ResponseEntity.ok(result);

        } catch (IllegalArgumentException e) {
            return ResponseEntity
                    .badRequest()
                    .body(java.util.Map.of(
                            "message", e.getMessage()));
        } catch (Exception e) {
            return ResponseEntity
                    .status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(java.util.Map.of( "message", "차량 등록 중 오류가 발생했습니다."));
        }
    }
}