package kr.co.alpharking.dao.vehicle;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import kr.co.alpharking.dto.vehicle.VehicleDTO;

@Mapper
public interface VehiceDao {

    void add(VehicleDTO vehicle);

    List<VehicleDTO> list();

    void update(VehicleDTO vehicle);

    void delete(@Param("vehicleid") Long vehicleId);
    
//    // 차량번호 중복 확인
//    int countByVehicleNumber(
//        @Param("officeid") Long officeid,
//        @Param("vehiclenumber") String vehiclenumber
//    ); => 추후 구현 예정
}