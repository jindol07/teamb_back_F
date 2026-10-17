package kr.co.alpharking.dao.parking;

import java.util.List;
import java.sql.Timestamp;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import kr.co.alpharking.dto.parking.ParkingUsageRow;

@Mapper
public interface ParkingUsageDao {
    Long lockRegisteredVehicle(@Param("number") String number);
    Long findOpenUsageByPlate(@Param("number") String number);
    int insertEntry(@Param("vehicleId") Long vehicleId, @Param("number") String number, @Param("parkingType") String parkingType, @Param("eventTime") Timestamp eventTime);
    Long insertedUsageId();
    java.sql.Timestamp findLatestExitByPlate(@Param("number") String number);
    Long findSpaceIdByCode(@Param("spaceCode") String spaceCode);
    ParkingUsageRow findById(@Param("id") Long id);
    ParkingUsageRow lockOpenUsage(@Param("id") Long id);
    List<ParkingUsageRow> findActive();
    List<ParkingUsageRow> findRecent();
    String lockSpaceStatus(@Param("spaceId") Long spaceId);
    int countOtherActiveOnSpace(@Param("spaceId") Long spaceId, @Param("usageId") Long usageId);
    int assignSpace(@Param("usageId") Long usageId, @Param("spaceId") Long spaceId);
    int exitUsage(@Param("usageId") Long usageId, @Param("eventTime") Timestamp eventTime);
}
