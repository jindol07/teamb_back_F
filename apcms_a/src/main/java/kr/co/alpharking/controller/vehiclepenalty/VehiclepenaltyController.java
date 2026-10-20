package kr.co.alpharking.controller.vehiclepenalty;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.vehiclepenalty.VehiclePenaltyDto;
import kr.co.alpharking.security.Admin;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.service.vehiclepenalty.VehiclepenaltyService;

@RestController
@RequestMapping("/api/vehiclepenalty")
public class VehiclepenaltyController {

	private final VehiclepenaltyService vehiclepenaltyService;

	public VehiclepenaltyController(VehiclepenaltyService vehiclepenaltyService) {
		this.vehiclepenaltyService = vehiclepenaltyService;
	}

	@PostMapping
	public ResponseEntity<Void> addVehiclePenalty(@RequestBody VehiclePenaltyDto vehiclePenalty, @AuthenticationPrincipal Object principal) {
        if (!(principal instanceof Admin) || ((Admin) principal).getAdmin_id() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        vehiclePenalty.setImposedbyadminid(((Admin) principal).getAdmin_id());
        vehiclepenaltyService.addVehiclePenalty(vehiclePenalty);
		return ResponseEntity.ok().build();
	}

	@GetMapping
	public ResponseEntity<List<VehiclePenaltyDto>> getVehiclePenalties() {
		return ResponseEntity.ok(vehiclepenaltyService.getVehiclePenalties());
	}

	@PutMapping("/{vehiclePenaltyId}")
	public ResponseEntity<Void> updateVehiclePenalty(
			@PathVariable("vehiclePenaltyId") Long vehiclePenaltyId,
			@RequestBody VehiclePenaltyDto vehiclePenalty) {
		vehiclePenalty.setVehiclepenaltyid(vehiclePenaltyId);
		vehiclepenaltyService.updateVehiclePenalty(vehiclePenalty);
		return ResponseEntity.ok().build();
	}

	@DeleteMapping("/{vehiclePenaltyId}")
	public ResponseEntity<Void> deleteVehiclePenalty(
			@PathVariable("vehiclePenaltyId") Long vehiclePenaltyId) {
		vehiclepenaltyService.deleteVehiclePenalty(vehiclePenaltyId);
		return ResponseEntity.ok().build();
	}
}
