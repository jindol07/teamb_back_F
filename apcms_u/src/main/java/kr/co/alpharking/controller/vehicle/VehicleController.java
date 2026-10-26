package kr.co.alpharking.controller.vehicle;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.vehicle.VehicleRegistrationRequestDto;
import kr.co.alpharking.entity.vehicle.Vehicle;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.service.vehicle.VehicleService;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/vehicles")
@RequiredArgsConstructor
public class VehicleController {

    private final VehicleService vehicleService;

    @GetMapping("/mine")
    public ResponseEntity<List<Vehicle>> getMyVehicles(@AuthenticationPrincipal Office office) {
        return ResponseEntity.ok(vehicleService.getVehiclesByOffice(office.getOffice_id()));
    }

    @PostMapping("/mine/requests")
    public ResponseEntity<Void> requestVehicleRegistration(
            @AuthenticationPrincipal Office office,
            @RequestBody VehicleRegistrationRequestDto request) {
        vehicleService.submitVehicleRegistrationRequest(office.getOffice_id(), request);
        return ResponseEntity.accepted().build();
    }

    @GetMapping("/number/{vehicleNumber}")
    public ResponseEntity<?> searchByVehicleNumber(@PathVariable("vehicleNumber") String vehicleNumber) {
        List<Vehicle> vehicleList = vehicleService.searchByVehicleNumber(vehicleNumber);
        if (vehicleList != null && !vehicleList.isEmpty()) {
            return ResponseEntity.ok(vehicleList);
        }
        return ResponseEntity.notFound().build();
    }

    @DeleteMapping("/{vehicleId}")
    public ResponseEntity<Void> deleteVehicle(
            @PathVariable("vehicleId") Long vehicleId,
            @AuthenticationPrincipal Office office) {
        vehicleService.deleteVehicle(vehicleId, office.getOffice_id());
        return ResponseEntity.noContent().build();
    }
}
