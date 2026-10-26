package kr.co.alpharking.dao.vehiclehistory;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import kr.co.alpharking.dto.vehiclehistory.VehiclehistoryDto;

@Mapper
public interface VehiclehistoryDao {
    void add(VehiclehistoryDto vehiclehistory);

    List<VehiclehistoryDto> list();
}
