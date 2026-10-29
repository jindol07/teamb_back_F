package kr.co.alpharking.security;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface SignupVehicleRepository extends JpaRepository<SignupVehicle, Long> {
	@Query(value = """
	    SELECT COUNT(*)
	    FROM VEHICLE
	    WHERE REPLACE(VEHICLE_NUMBER, ' ', '') = REPLACE(:vehicle_number, ' ', '')
	    """, nativeQuery = true)
	Long countDuplicateVehicleNumber(
	    @Param("vehicle_number") String vehicle_number
	);
}
