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

    @Transactional(readOnly = true)
    public List<DailyParkingSummaryRow> recentDailySummary(String period) {
        final int days;
        if ("week".equals(period)) days = 7;
        else if ("month".equals(period)) days = 30;
        else throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "period는 week 또는 month여야 합니다.");
        LocalDate today = LocalDate.now(KST);
        return dao.findDailySummary(today.minusDays(days - 1L).toString(), today.plusDays(1).toString());
    }

    @Transactional(readOnly = true)
    public List<DashboardParkingEventRow> recentParkingEvents() {
        return dao.findRecentParkingEvents();
    }
}
