package kr.co.alpharking.dao.parking;

import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;

@Mapper
public interface ParkingSpaceDao {
    List<ParkingSpaceRow> findAllAdmin();
    List<ParkingSpacePublicRow> findAllPublic();
}
