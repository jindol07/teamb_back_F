package kr.co.alpharking.service.vehicle;

import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import kr.co.alpharking.entity.vehicle.Vehicle;
import kr.co.alpharking.repository.vehicle.VehicleRepository;

@Service
public class VehicleService {
	
	@Autowired
	private VehicleRepository vehicleRepository;
	
	// 1. 차량번호 조회 (기존 기능)
	public Optional<Vehicle> findByVehicleNumber(String vehicleNumber) {
		
		System.out.println("===== VehicleService =====");
		System.out.println("조회 번호 : " + vehicleNumber);
		
		return vehicleRepository.findByVehicleNumber(vehicleNumber);
	}
	
	// 2. 승인된 등록 차량 조회 (추가)
	public Optional<Vehicle> findRegisteredVehicleByNumber(String vehicleNumber) {
		return vehicleRepository.findByVehicleNumberAndRegistrationStatusCodeAndDeletedAtIsNull(vehicleNumber,"REGISTERED");
	}
	
}