package kr.co.alpharking.dto.dashboard;

import org.apache.ibatis.type.Alias;
import lombok.Data;

/** dashboard.xml → 관리자 Chart.js 데이터. 단위는 주차·예약 건수다. */
@Data
@Alias("DailyParkingSummaryRow")
public class DailyParkingSummaryRow {
    private String summaryDate;
    private Long usageCount;
    private Long reservationCount;
    private Long visitorCount;
}
