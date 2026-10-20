package kr.co.alpharking.dao.vehiclepenalty;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import kr.co.alpharking.dto.vehiclepenalty.VehiclePenaltyDto;

@Mapper
public interface VehiclePenaltyDao {

	void add(VehiclePenaltyDto vehiclePenalty);

	List<VehiclePenaltyDto> list();

	void update(VehiclePenaltyDto vehiclePenalty);

	void delete(@Param("vehiclepenaltyid") Long vehiclePenaltyId);
}
