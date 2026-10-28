/** 파일 안내
 * 용도: 저장된 하루 단위 주차·예약·방문 차량 이용 통계 응답.
 * 직접 사용처: dashboard.xml.findDailySummary → DashboardDao/Service/Controller → VehicleBarChart.
 * MyBatis Alias는 클래스명과 같다. 실시간 점유 면수가 아니라 날짜별 이용 건수를 표현한다.
 */
package kr.co.alpharking.dto.dashboard;

import org.apache.ibatis.type.Alias;
import lombok.Data;

/** dashboard.xml → 관리자 Chart.js 데이터. 단위는 주차·예약 건수다. */
@Data
@Alias("DailyParkingSummaryRow")
public class DailyParkingSummaryRow {
    /** SQL에서 YYYY-MM-DD로 변환한 집계 기준일. */
    private String summaryDate;
    /** 해당 날짜에 저장된 전체 주차 이용 건수. */
    private Long usageCount;
    /** 해당 날짜에 저장된 예약 건수. 현재 구획의 RESERVED 상태 수와 다르다. */
    private Long reservationCount;
    /** 방문 차량 이용 건수. 전체 이용 건수와 더해 총계를 만들지 않는다. */
    private Long visitorCount;
}
