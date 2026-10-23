package kr.co.alpharking.repository.vehicle;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import kr.co.alpharking.entity.vehicle.Vehicle;

public interface VehicleRepository extends JpaRepository<Vehicle, Long> {
    Optional<Vehicle> findByVehicleNumber(String vehicleNumber);

    List<Vehicle> findByOfficeIdAndDeletedAtIsNullAndRegistrationStatusCodeIn(
            Long officeId, List<String> registrationStatusCodes);

    boolean existsByVehicleNumberAndRegistrationStatusCodeInAndDeletedAtIsNull(
            String vehicleNumber, List<String> registrationStatusCodes);

    long countByOfficeIdAndDeletedAtIsNullAndRegistrationStatusCodeIn(
            Long officeId, List<String> registrationStatusCodes);

    List<Vehicle> findByVehicleNumberContaining(String vehicleNumber);

    Optional<Vehicle> findByVehicleNumberAndRegistrationStatusCodeAndDeletedAtIsNull(
            String vehicleNumber,
            String registrationStatusCode
    );
}
