/** 파일 안내
 * 용도: 대시보드 통계 기간을 검증하고 일별 집계·최근 입출차를 읽는다.
 * 직접 사용처: DashboardController → DashboardDao → mapper/dashboard.xml.
 * week는 오늘 포함 7일, month는 오늘 포함 30일이다. 달력상의 월 전체 조회는 아니다.
 * 읽기 전용 트랜잭션이며 DAILY_PARKING_SUMMARY 집계를 새로 생성하거나 원본 이용 기록을 변경하지 않는다.
 */
package kr.co.alpharking.service.dashboard;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dao.dashboard.DashboardDao;
import kr.co.alpharking.dto.dashboard.DailyParkingSummaryRow;
import kr.co.alpharking.dto.dashboard.DashboardParkingEventRow;

/** 한국 날짜 기준 주간·월간 집계와 최근 입출차 조회. 원본 데이터는 변경하지 않는다. */
@Service
public class DashboardService {
    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private final DashboardDao dao;

    public DashboardService(DashboardDao dao) { this.dao = dao; }

    /** 한국 날짜 기준 시작일 포함·종료일 제외 범위를 만든다. 지원하지 않는 기간은 400으로 거절한다. */
    @Transactional(readOnly = true)
    public List<DailyParkingSummaryRow> recentDailySummary(String period) {
        final int days;
        if ("week".equals(period)) days = 7;
        else if ("month".equals(period)) days = 30;
        else throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "period는 week 또는 month여야 합니다.");
        LocalDate today = LocalDate.now(KST);
        return dao.findDailySummary(today.minusDays(days - 1L).toString(), today.plusDays(1).toString());
    }

    /** 입차·출차를 각각 이벤트로 펼친 최근 5건을 SQL의 정렬·제한 기준 그대로 반환한다. */
    @Transactional(readOnly = true)
    public List<DashboardParkingEventRow> recentParkingEvents() {
        return dao.findRecentParkingEvents();
    }
}
