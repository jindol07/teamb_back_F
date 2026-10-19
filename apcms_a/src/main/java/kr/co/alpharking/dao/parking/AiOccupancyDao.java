package kr.co.alpharking.dao.parking;

import java.time.LocalDateTime;
import java.util.Map;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;

@Mapper
public interface AiOccupancyDao {
    ParkingSpaceRow lockByCode(@Param("spaceCode") String spaceCode);
    int countEventId(@Param("parkingSpaceId") Long id, @Param("needle") String needle);
    LocalDateTime latestOccupancyDetectedAt(@Param("parkingSpaceId") Long id);
    int insertEvent(Map<String, Object> params);
    int updateStatus(@Param("parkingSpaceId") Long id, @Param("status") String status);
    int closeHistory(@Param("parkingSpaceId") Long id);
    int insertHistory(@Param("parkingSpaceId") Long id,
                      @Param("aiDetectionEventId") Long eventId);
}
