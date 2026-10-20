package kr.co.alpharking.service.vehicle;

import java.util.List;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import kr.co.alpharking.entity.vehicle.Vehicle;
import kr.co.alpharking.repository.vehicle.VehicleRepository;

@Service
public class VehicleService {

    @Autowired
    private VehicleRepository vehicleRepository;

    // 차량번호 조회
    public Optional<Vehicle> findByVehicleNumber(String vehicleNumber) {
        System.out.println("===== VehicleService (단건 조회) =====");
        System.out.println("조회 번호 : " + vehicleNumber);
        return vehicleRepository.findByVehicleNumber(vehicleNumber);
    }

    // 차량번호 일부 검색
    public List<Vehicle> searchByVehicleNumber(String vehicleNumber) {
        System.out.println("===== VehicleService (일부 검색) =====");
        System.out.println("조회 번호 : " + vehicleNumber);
        return vehicleRepository.findByVehicleNumberContaining(vehicleNumber);
    }

    // 승인된 등록 차량 조회
    public Optional<Vehicle> findRegisteredVehicleByNumber(String vehicleNumber) {
        System.out.println("===== VehicleService (승인 등록 차량 조회) =====");
        System.out.println("조회 번호 : " + vehicleNumber);
        return vehicleRepository.findByVehicleNumberAndRegistrationStatusCodeAndDeletedAtIsNull(
                vehicleNumber, "REGISTERED");
    }
}