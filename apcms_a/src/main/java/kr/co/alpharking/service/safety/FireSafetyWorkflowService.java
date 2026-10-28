package kr.co.alpharking.service.safety;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.Set;
import kr.co.alpharking.dao.safety.FireSafetyWorkflowDao;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

/** AI 탐지 상태와 관리자의 업무 상태는 서로 독립적으로 관리합니다. */
@Service
public class FireSafetyWorkflowService {
    private static final Map<String, Set<String>> ALLOWED = Map.of(
            "RECEIVED", Set.of("PROCESSING", "HOLD", "RESOLVED"),
            "PROCESSING", Set.of("HOLD", "RESOLVED"),
            "HOLD", Set.of("PROCESSING", "RESOLVED"),
            "RESOLVED", Set.of());

    private final FireSafetyWorkflowDao dao;

    public FireSafetyWorkflowService(FireSafetyWorkflowDao dao) {
        this.dao = dao;
    }

    static String validateRequest(Long incidentId, Long adminId,
                                  String status, String note) {
        if (incidentId == null || incidentId <= 0 || adminId == null || adminId <= 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "사건/관리자 ID가 잘못되었습니다.");
        }
        if (status == null || !Set.of("PROCESSING", "HOLD", "RESOLVED").contains(status)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "지원하지 않는 목표 상태입니다.");
        }
        if ("RESOLVED".equals(status)) {
            // 즉시 완료는 메모 없이 허용한다. 기존 클라이언트가 보내는 선택 메모는 길이만 검증한다.
            if (note == null || note.isBlank()) return null;
            String normalized = note.strip();
            if (normalized.getBytes(StandardCharsets.UTF_8).length > 500) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "해결 메모는 UTF-8 기준 500바이트 이하여야 합니다.");
            }
            return normalized;
        }
        if (note != null && !note.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "해결 메모는 RESOLVED 변경에서만 전송하세요.");
        }
        return null;
    }

    static void validateTransition(String previous, String next) {
        if (!ALLOWED.getOrDefault(previous, Set.of()).contains(next)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "허용되지 않은 사건 상태 전환: " + previous + " -> " + next);
        }
    }

    @Transactional
    public Map<String, Object> change(Long incidentId, Long adminId,
                                      String targetStatus, String resolutionNote) {
        String note = validateRequest(incidentId, adminId, targetStatus, resolutionNote);
        String previous = dao.lockCurrentStatus(incidentId);
        if (previous == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "사건을 찾을 수 없습니다.");
        }
        // 중복 클릭·응답 유실 후 재시도·다른 관리자와의 동시 완료는 기존 완료 정보를 보존한다.
        if ("RESOLVED".equals(previous) && "RESOLVED".equals(targetStatus)) {
            return dao.current(incidentId);
        }
        validateTransition(previous, targetStatus);
        int changed = "RESOLVED".equals(targetStatus)
                ? dao.resolve(incidentId, adminId, note)
                : dao.changeOpenStatus(incidentId, adminId, targetStatus);
        if (changed != 1) {
            throw new IllegalStateException("사건 변경 행 수가 1이 아닙니다.");
        }
        return dao.current(incidentId);
    }
}
