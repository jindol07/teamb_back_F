package kr.co.alpharking.service.safety;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;
import java.util.Set;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.safety.FireSafetyRequest;

/** 위험도와 confidence는 별개. confidence는 [0,1]의 탐지 신뢰도일 뿐입니다. */
public final class FireSafetyValidator {
    private static final Pattern SHA = Pattern.compile("[a-f0-9]{64}");
    private static final Pattern SIMPLE = Pattern.compile("[a-zA-Z0-9_.-]{1,128}");
    private FireSafetyValidator() {}
    private static void bad(String detail) {
        throw new ResponseStatusException(HttpStatus.BAD_REQUEST, detail);
    }
    public static OffsetDateTime time(String text, String name) {
        try {
            OffsetDateTime date = OffsetDateTime.parse(text);
            if (!ZoneOffset.UTC.equals(date.getOffset())) bad(name + "은 UTC 시각이어야 합니다.");
            return date;
        } catch (DateTimeParseException | NullPointerException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, name + " 형식 오류", ex);
        }
    }
    public static void validate(FireSafetyRequest r, String header) {
        if (r == null) bad("요청 본문이 필요합니다.");
        if (!"1.0".equals(r.schemaVersion())) bad("지원하지 않는 schema_version");
        if (r.transitionId() == null || !SHA.matcher(r.transitionId()).matches()) bad("transition_id는 64자 SHA-256이어야 합니다.");
        if (!r.transitionId().equals(header)) bad("X-Idempotency-Key 불일치");
        if (r.incidentId() == null || !SIMPLE.matcher(r.incidentId()).matches()) bad("incident_id 형식 오류");
        if (r.regionId() == null || !SIMPLE.matcher(r.regionId()).matches()) bad("region_id 형식 오류");
        if (r.hazardType() == null || !Set.of("FIRE", "SMOKE").contains(r.hazardType())) bad("FIRE/SMOKE만 지원합니다.");
        if (r.status() == null || !Set.of("SUSPECTED", "REOPENED", "CLEARED").contains(r.status())) bad("지원하지 않는 AI 상태입니다.");
        time(r.observedAtUtc(), "observed_at_utc");
        time(r.sessionStartedAtUtc(), "session_started_at_utc");
        if (r.source() == null || r.source().kind() == null || !Set.of("CAMERA", "VIDEO").contains(r.source().kind())
            || r.source().name() == null || !SIMPLE.matcher(r.source().name()).matches()) bad("source 형식 오류");
        if (r.confidence() == null || r.confidence().compareTo(BigDecimal.ZERO) < 0
            || r.confidence().compareTo(BigDecimal.ONE) > 0) bad("confidence는 0~1입니다.");
        if (r.sourceSeconds() == null || r.sourceSeconds().signum() < 0
            || r.sourceSeconds().compareTo(new BigDecimal("31536000")) > 0) bad("source_seconds 범위 오류");
        if (r.frameIndex() == null || r.frameIndex() < 0 || r.hitsInWindow() == null || r.hitsInWindow() < 0)
            bad("프레임/감지 횟수는 비음수여야 합니다.");
        var b = r.bboxXyxy();
        if (b == null || b.size() != 4 || b.stream().anyMatch(v -> v == null || v < 0 || v > 1_000_000)
           || b.get(0) >= b.get(2) || b.get(1) >= b.get(3)) bad("bbox_xyxy 형식 오류");
        if (r.reason() != null && r.reason().length() > 300) bad("reason 너무 김");
        if (r.isTest() == null || r.requiresHumanReview() == null || !r.requiresHumanReview())
            bad("is_test 및 requires_human_review=true가 필요합니다.");
    }
}
