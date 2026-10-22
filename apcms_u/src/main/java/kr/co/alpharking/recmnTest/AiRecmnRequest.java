package kr.co.alpharking.recmnTest;

import java.time.LocalDateTime;
import java.util.List;

// POST /api/recmn/predict 요청
public record AiRecmnRequest(
        Long officeId,
        LocalDateTime reservationAt,
        List<UsageRecord> history
) {
    // 사용자의 과거 주차 이용 기록
    public record UsageRecord(
            LocalDateTime entryAt,
            String zoneCode
    ) {
    }
}