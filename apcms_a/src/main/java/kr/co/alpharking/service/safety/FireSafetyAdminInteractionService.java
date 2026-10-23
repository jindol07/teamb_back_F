package kr.co.alpharking.service.safety;

import java.util.Map;
import kr.co.alpharking.dao.safety.FireSafetyAdminInteractionDao;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

/** 1. 안전사고 상세와 안전 알림 읽음 처리 업무 규칙. */
@Service
public class FireSafetyAdminInteractionService {
    private final FireSafetyAdminInteractionDao dao;

    public FireSafetyAdminInteractionService(FireSafetyAdminInteractionDao dao) {
        this.dao = dao;
    }

    /** 2. 관리자 권한 검사는 Controller에서 하고 여기서는 사건 유무를 확인합니다. */
    @Transactional(readOnly = true)
    public Map<String, Object> incidentDetail(Long incidentId) {
        positiveId(incidentId, "사건 ID");
        Map<String, Object> row = dao.incidentDetail(incidentId);
        if (row == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "사건을 찾을 수 없습니다.");
        }
        return row;
    }

    /**
     * 3. 읽음 처리: JWT에 담긴 관리자 ID로 소유권을 제한합니다.
     * 3-1. 기존 읽음 데이터는 변경하지 않아 여러 번 호출해도 READ_AT이 유지됩니다.
     * 3-2. 이 작업은 SAFETY_INCIDENT의 업무 상태를 변경하지 않습니다.
     */
    @Transactional
    public Map<String, Object> readNotification(Long notificationId, Long adminId) {
        positiveId(notificationId, "알림 ID");
        positiveId(adminId, "관리자 ID");
        String state = dao.lockOwnNotificationReadStatus(notificationId, adminId);
        if (state == null) {
            // 다른 관리자 소유의 존재 여부가 노출되지 않도록 404를 반환합니다.
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "안전 알림을 찾을 수 없습니다.");
        }
        if (shouldMarkRead(state)) {
            int count = dao.markOwnNotificationRead(notificationId, adminId);
            if (count != 1) {
                throw new IllegalStateException("알림 읽음 처리 갱신 건수가 1이 아닙니다.");
            }
        }
        Map<String, Object> result = dao.ownNotification(notificationId, adminId);
        if (result == null) {
            throw new IllegalStateException("읽음 처리한 알림의 재조회에 실패했습니다.");
        }
        return result;
    }

    /** 4. 읽음 상태는 N 또는 Y만 정상 데이터로 허용합니다. */
    static boolean shouldMarkRead(String state) {
        return switch (state) {
            case "N" -> true;
            case "Y" -> false;
            default -> throw new IllegalStateException("지원하지 않는 알림 읽음 상태입니다.");
        };
    }

    /** 5. 양의 정수 ID만 받습니다. */
    static void positiveId(Long id, String label) {
        if (id == null || id <= 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, label + "가 잘못되었습니다.");
        }
    }
}
