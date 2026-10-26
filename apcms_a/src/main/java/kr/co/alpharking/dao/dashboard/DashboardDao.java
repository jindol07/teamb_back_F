package kr.co.alpharking.dao.dashboard;

import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import kr.co.alpharking.dto.dashboard.DailyParkingSummaryRow;
import kr.co.alpharking.dto.dashboard.DashboardParkingEventRow;

/** DashboardService → mapper/dashboard.xml의 읽기 전용 통계 조회. */
@Mapper
public interface DashboardDao {
    List<DailyParkingSummaryRow> findDailySummary(@Param("startDate") String startDate,
                                                @Param("endDate") String endDate);

    List<DashboardParkingEventRow> findRecentParkingEvents();
}
