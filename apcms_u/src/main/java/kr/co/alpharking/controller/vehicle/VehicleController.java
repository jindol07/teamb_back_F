package kr.co.alpharking.controller.vehicle;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.entity.vehicle.Vehicle;
import kr.co.alpharking.service.vehicle.VehicleService;

@RestController
@RequestMapping("/api/vehicles")
public class VehicleController {

	@Autowired
	private VehicleService vehicleService;

	// http://192.168.0.23/alpharking/api/vehicles/number/12 (일부 검색 지원)
	@GetMapping("/number/{vehicleNumber}")
	public ResponseEntity<?> searchByVehicleNumber(@PathVariable("vehicleNumber") String vehicleNumber) {

		System.out.println("===== VehicleController (일부 검색) =====");
		System.out.println("검색어 : " + vehicleNumber);

		List<Vehicle> vehicleList = vehicleService.searchByVehicleNumber(vehicleNumber);

		System.out.println("조회된 차량 수 : " + vehicleList.size());

		// 검색 결과가 존재하면 리스트 반환
		if (vehicleList != null && !vehicleList.isEmpty()) {
			return ResponseEntity.ok(vehicleList);
		}

		// 결과가 없으면 빈 리스트 혹은 404 처리 (여기서는 빈 리스트 또는 404)
		return ResponseEntity.notFound().build();
	}
}