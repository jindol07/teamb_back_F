package kr.co.alpharking.repository.vehicle;

import org.springframework.data.jpa.repository.JpaRepository;

import kr.co.alpharking.entity.vehicle.VehicleChangeRequest;

public interface VehicleChangeRequestRepository extends JpaRepository<VehicleChangeRequest, Long> {
    boolean existsByOfficeIdAndRequestedVehicleNumberAndRequestStatusCode(
            Long officeId, String requestedVehicleNumber, String requestStatusCode);
}
