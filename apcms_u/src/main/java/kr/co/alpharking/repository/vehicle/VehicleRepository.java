package kr.co.alpharking.repository.vehicle;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import kr.co.alpharking.entity.vehicle.Vehicle;

public interface VehicleRepository extends JpaRepository<Vehicle, Long> {

    // 차량번호 조회
    Optional<Vehicle> findByVehicleNumber(String vehicleNumber);

    // 차량번호 일부 검색
    List<Vehicle> findByVehicleNumberContaining(String vehicleNumber);

    // 승인된 등록 차량 중 삭제되지 않은 차량 조회
    Optional<Vehicle> findByVehicleNumberAndRegistrationStatusCodeAndDeletedAtIsNull(
            String vehicleNumber,
            String registrationStatusCode
    );
}