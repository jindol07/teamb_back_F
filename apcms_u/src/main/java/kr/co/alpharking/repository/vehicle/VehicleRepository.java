package kr.co.alpharking.repository.vehicle;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import kr.co.alpharking.entity.vehicle.Vehicle;

public interface VehicleRepository extends JpaRepository<Vehicle, Long> {
	
//  1. 차량번호로 조회
    Optional<Vehicle> findByVehicleNumber(String vehicleNumber);
    
//  2. 승인된 등록 차량 중 삭제되지 않은 차량 조회
//  조건에 맞는 데이터를 조회해서 차량번호가 일치하는지 확인하고 등록 상태가 일치하는지 확인하고 삭제 날짜가 NULL인지 확인함
    Optional<Vehicle> findByVehicleNumberAndRegistrationStatusCodeAndDeletedAtIsNull(
            String vehicleNumber,
            String registrationStatusCode
    );
    
}