package kr.co.alpharking.repository.vehicle;

import kr.co.alpharking.entity.vehicle.FavoriteVisitorVehicle;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface FavoriteVisitorVehicleRepository extends JpaRepository<FavoriteVisitorVehicle, Long> {

    // 1. 특정 오피스(OFFICE_ID)에 등록된 방문자 차량 목록 조회
    List<FavoriteVisitorVehicle> findByOfficeId(Long officeId);

    // 2. 차량 번호로 조회
    List<FavoriteVisitorVehicle> findByVehicleNumber(String vehicleNumber);
}