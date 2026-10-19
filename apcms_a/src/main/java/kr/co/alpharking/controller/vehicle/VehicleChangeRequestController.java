package kr.co.alpharking.controller.vehicle;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.vehicle.VehicleChangeRequestDTO;
import kr.co.alpharking.service.vehicle.VehicleChangeRequestService;

@RestController
@RequestMapping("/api/vehiclech")
public class VehicleChangeRequestController {

	private final VehicleChangeRequestService vehicleChangeRequestService;

	public VehicleChangeRequestController(VehicleChangeRequestService vehicleChangeRequestService) {
		this.vehicleChangeRequestService = vehicleChangeRequestService;
	}

	// 차량 변경 요청 등록
	@PostMapping
	public ResponseEntity<Void> addVehicleChangeRequest(@RequestBody VehicleChangeRequestDTO vehicleChangeRequest) {
		vehicleChangeRequestService.addVehicleChangeRequest(vehicleChangeRequest);
		return ResponseEntity.ok().build();
	}

	// 차량 변경 요청 검토 (승인 / 반려)
	@PutMapping("/{vehicleChangeRequestId}")
	public ResponseEntity<Void> updateVehicleChangeRequest(
			@PathVariable("vehicleChangeRequestId") Long vehicleChangeRequestId,
			@RequestBody VehicleChangeRequestDTO vehicleChangeRequest) {
		vehicleChangeRequest.setVehiclechangerequestid(vehicleChangeRequestId);
		vehicleChangeRequestService.updateVehicleChangeRequest(vehicleChangeRequest);
		return ResponseEntity.ok().build();
	}

	// 차량 변경 요청 목록 조회
	@GetMapping
	public ResponseEntity<List<VehicleChangeRequestDTO>> getVehicleChangeRequests() {
		List<VehicleChangeRequestDTO> requests = vehicleChangeRequestService.getVehicleChangeRequests();

		return ResponseEntity.ok(requests);
	}

	// 차량 변경 요청 취소
	@DeleteMapping("/{vehicleChangeRequestId}")
	public ResponseEntity<Void> deleteVehicleChangeRequest(
			@PathVariable("vehicleChangeRequestId") Long vehicleChangeRequestId) {
		vehicleChangeRequestService.deleteVehicleChangeRequest(vehicleChangeRequestId);
		return ResponseEntity.ok().build();
	}
}