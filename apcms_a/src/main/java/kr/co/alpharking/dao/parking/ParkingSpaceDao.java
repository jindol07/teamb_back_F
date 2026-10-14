package kr.co.alpharking.dao.parking;

import java.util.List;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Mapper;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;

@Mapper
public interface ParkingSpaceDao {
    List<ParkingSpaceRow> findAllAdmin();
    List<ParkingSpacePublicRow> findAllPublic();
    ParkingSpaceRow lockForUpdate(@Param("id") Long id);
    int updateAdminSpace(@Param("id") Long id, @Param("status") String status,
                         @Param("type") String type, @Param("memo") String memo);
    int closeOpenHistory(@Param("id") Long id);
    int insertAdminHistory(@Param("id") Long id, @Param("adminId") Long adminId,
                           @Param("reason") String reason);
    ParkingSpaceRow findById(@Param("id") Long id);
}
