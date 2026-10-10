package kr.co.alpharking.repository.vehicle;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import kr.co.alpharking.entity.vehicle.Vehicle;

public interface VehicleRepository extends JpaRepository<Vehicle, Long> {

	Optional<Vehicle> findByVehicleNumber(String vehicleNumber);

}