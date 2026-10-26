package kr.co.alpharking.repository.vehicle;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.entity.vehicle.Vehicle;

public interface VehicleRepository extends JpaRepository<Vehicle, Long> {
    Optional<Vehicle> findByVehicleNumber(String vehicleNumber);

    List<Vehicle> findByOfficeIdAndDeletedAtIsNullAndRegistrationStatusCodeIn(
            Long officeId, List<String> registrationStatusCodes);

    boolean existsByVehicleNumberAndRegistrationStatusCodeInAndDeletedAtIsNull(
            String vehicleNumber, List<String> registrationStatusCodes);

    long countByOfficeIdAndDeletedAtIsNullAndRegistrationStatusCodeIn(
            Long officeId, List<String> registrationStatusCodes);

    @Query(value = "SELECT * FROM VEHICLE " +
            "WHERE VEHICLE_NUMBER LIKE '%' || :vehicleNumber || '%' " +
            "ORDER BY VEHICLE_ID ASC", nativeQuery = true)
    List<Vehicle> searchByVehicleNumberContaining(@Param("vehicleNumber") String vehicleNumber);

    Optional<Vehicle> findByVehicleNumberAndRegistrationStatusCodeAndDeletedAtIsNull(
            String vehicleNumber,
            String registrationStatusCode
    );
}
