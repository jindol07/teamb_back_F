package kr.co.alpharking.controller.vehicle;

import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.entity.vehicle.Vehicle;
import kr.co.alpharking.service.vehicle.VehicleService;

// 번호판으로 VEHICLE 테이블 조회(차량 조회)가 되는지 확인하는 단독 테스트 용도
@RestController
@RequestMapping("/api/vehicles")
public class VehicleController {

	@Autowired
	private VehicleService vehicleService;

//	http://192.168.0.23/alpharking/api/vehicles/number/91소6408
	@GetMapping("/number/{vehicleNumber}")
	public ResponseEntity<?> findByVehicleNumber(@PathVariable("vehicleNumber") String vehicleNumber) {

		System.out.println("===== VehicleController =====");
		System.out.println("vehicleNumber : " + vehicleNumber);

		Optional<Vehicle> vehicle = vehicleService.findByVehicleNumber(vehicleNumber);

		System.out.println("조회 결과 : " + vehicle);

		if (vehicle.isPresent()) {
			return ResponseEntity.ok(vehicle.get());
		}

		return ResponseEntity.notFound().build();
	}
}