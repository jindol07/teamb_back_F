/** 파일 안내
 * 용도: 대시보드 일별 통계·최근 입출차 SQL을 연결하는 MyBatis 인터페이스.
 * 직접 사용처: DashboardService. namespace와 메서드명은 mapper/dashboard.xml의 statement id에 대응한다.
 * 날짜 경계는 서비스에서 계산하고 조회 결과는 대시보드 전용 DTO로 반환한다. 쓰기 메서드는 없다.
 */
package kr.co.alpharking.dao.dashboard;

import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import kr.co.alpharking.dto.dashboard.DailyParkingSummaryRow;
import kr.co.alpharking.dto.dashboard.DashboardParkingEventRow;

/** DashboardService → mapper/dashboard.xml의 읽기 전용 통계 조회. */
@Mapper
public interface DashboardDao {
    /** startDate 이상 endDate 미만의 저장된 일별 통계만 날짜순으로 조회한다. */
    List<DailyParkingSummaryRow> findDailySummary(@Param("startDate") String startDate,
                                                @Param("endDate") String endDate);

    /** 전체 이용 기록의 입차·출차 시각을 합쳐 발생 시각 기준 최신 5건을 조회한다. */
    List<DashboardParkingEventRow> findRecentParkingEvents();
}
