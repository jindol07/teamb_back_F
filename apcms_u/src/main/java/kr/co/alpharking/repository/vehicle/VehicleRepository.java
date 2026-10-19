package kr.co.alpharking.repository.vehicle;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import kr.co.alpharking.entity.vehicle.Vehicle;

public interface VehicleRepository extends JpaRepository<Vehicle, Long> {
    
    // 기존 단건 조회 "123가 4567"
    Optional<Vehicle> findByVehicleNumber(String vehicleNumber);

    // 일부 검색을 위한 메서드 추가 "12"만 입력해도 됨
    List<Vehicle> findByVehicleNumberContaining(String vehicleNumber);
}