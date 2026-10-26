package kr.co.alpharking.controller.report;

import java.util.List;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.security.Admin;

@RestController
@RequestMapping("/api/reports")
public class ReportReviewController {
    private final JdbcTemplate jdbc;

    public ReportReviewController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @GetMapping
    public List<Map<String, Object>> list(@AuthenticationPrincipal Object principal) {
        requireAdmin(principal);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT r.report_id AS reportid, r.office_id AS reporterofficeid,
                       r.target_vehicle_id AS targetvehicleid,
                       r.target_vehicle_number AS targetvehiclenumber,
                       r.parking_space_id AS parkingspaceid,
                       r.report_type_code AS reporttypecode, r.content,
                       r.status_code AS statuscode, r.review_reason AS reviewreason,
                       r.reviewer_admin_id AS revieweradminid,
                       r.reviewed_at AS reviewedat, r.created_at AS createdat,
                       o.office_number AS reporterofficenumber
                FROM report r LEFT JOIN office o ON o.office_id = r.office_id
                ORDER BY r.created_at DESC, r.report_id DESC
                """);
        return normalizeRows(rows);
    }

    @GetMapping("/history")
    public List<Map<String, Object>> history(@AuthenticationPrincipal Object principal) {
        requireAdmin(principal);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT h.report_history_id AS reporthistoryid,
                       h.report_id AS reportid,
                       h.office_id AS reporterofficeid,
                       o.office_number AS reporterofficenumber,
                       h.target_vehicle_id AS targetvehicleid,
                       h.target_vehicle_number AS targetvehiclenumber,
                       h.parking_space_id AS parkingspaceid,
                       h.report_type_code AS reporttypecode,
                       h.content,
                       h.status_code AS statuscode,
                       h.reviewer_admin_id AS revieweradminid,
                       h.review_reason AS reviewreason,
                       h.reviewed_at AS reviewedat,
                       h.created_at AS createdat,
                       h.changed_by_admin_id AS changedbyadminid,
                       h.actor_type_code AS actortypecode,
                       h.actor_id AS actorid,
                       h.change_type_code AS changetypecode,
                       h.change_reason AS changereason,
                       h.valid_from AS validfrom,
                       h.valid_to AS validto
                FROM report_history h
                LEFT JOIN office o ON o.office_id = h.office_id
                ORDER BY h.valid_from DESC, h.report_history_id DESC
                """);
        return normalizeRows(rows);
    }

    @PatchMapping("/{reportId}/review")
    @Transactional
    public Map<String, Object> review(@PathVariable("reportId") Long reportId,
            @RequestBody ReviewRequest request,
            @AuthenticationPrincipal Object principal) {
        Admin admin = requireAdmin(principal);
        if (request == null || !("ACCEPTED".equals(request.statusCode) || "REJECTED".equals(request.statusCode))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "처리 상태는 ACCEPTED 또는 REJECTED여야 합니다.");
        }
        Map<String, Object> report;
        try {
            report = jdbc.queryForMap("SELECT report_id, office_id, target_vehicle_id, target_vehicle_number, parking_space_id, report_type_code, content, status_code FROM report WHERE report_id = ? FOR UPDATE", reportId);
        } catch (org.springframework.dao.EmptyResultDataAccessException ex) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "신고를 찾을 수 없습니다.");
        }
        if (!"RECEIVED".equals(String.valueOf(report.get("STATUS_CODE")))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 처리된 신고입니다.");
        }

        Long reporterOfficeId = ((Number) report.get("OFFICE_ID")).longValue();
        String message;
        if ("ACCEPTED".equals(request.statusCode)) {
            if (request.penaltyAmount == null || request.rewardAmount == null
                    || request.penaltyAmount <= 0 || request.rewardAmount <= 0) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "패널티와 보상 마일리지는 1 이상으로 입력해야 합니다.");
            }
            String vehicleNumber = String.valueOf(report.get("TARGET_VEHICLE_NUMBER"));
            Map<String, Object> vehicle;
            try {
                vehicle = jdbc.queryForMap("SELECT vehicle_id, office_id FROM vehicle WHERE vehicle_number = ? AND deleted_at IS NULL AND ROWNUM = 1", vehicleNumber);
            } catch (org.springframework.dao.EmptyResultDataAccessException ex) {
                throw new ResponseStatusException(HttpStatus.NOT_FOUND, "신고 대상 차량을 찾을 수 없습니다.");
            }
            Long vehicleId = ((Number) vehicle.get("VEHICLE_ID")).longValue();
            Long targetOfficeId = vehicle.get("OFFICE_ID") == null ? null : ((Number) vehicle.get("OFFICE_ID")).longValue();
            String violationType = (request.violationTypeCode == null || request.violationTypeCode.isBlank())
                    ? String.valueOf(report.get("REPORT_TYPE_CODE")) : request.violationTypeCode;
            jdbc.update("INSERT INTO vehicle_penalty (vehicle_penalty_id, vehicle_id, violation_type_code, penalty_amount, reason, imposed_by_admin_id, imposed_at, status_code) VALUES (SEQ_VEHICLE_PENALTY.NEXTVAL, ?, ?, ?, ?, ?, SYSDATE, '미조치')",
                    vehicleId, violationType, request.penaltyAmount, request.reviewReason, admin.getAdmin_id());
            if (request.rewardAmount > 0) {
                jdbc.update("INSERT INTO mileage_history (mileage_history_id, mileage_type_code, amount, reference_type_code, reference_id, description, created_at, office_id) VALUES (SEQ_MILEAGE_HISTORY.NEXTVAL, 'REPORT_REWARD', ?, 'REPORT', ?, ?, SYSDATE, ?)",
                        request.rewardAmount, reportId, "신고 승인 보상", reporterOfficeId);
            }
            if (targetOfficeId != null) {
                insertUserNotification(targetOfficeId, "REPORT_PENALTY", "신고 검토 결과", "등록 차량 " + vehicleNumber + "에 신고 검토 결과 패널티가 부과되었습니다.", reportId);
            }
            message = "신고가 승인되어 패널티와 보상 처리가 완료되었습니다.";
            insertUserNotification(reporterOfficeId, "REPORT_REWARD", "신고 승인", request.rewardAmount + " 마일리지가 적립되었습니다.", reportId);
        } else {
            message = "신고가 검토 후 승인되지 않았습니다.";
            insertUserNotification(reporterOfficeId, "REPORT_REJECTED", "신고 검토 결과", message, reportId);
        }

        jdbc.update("UPDATE report SET status_code = ?, review_reason = ?, reviewer_admin_id = ?, reviewed_at = SYSDATE WHERE report_id = ?",
                request.statusCode, request.reviewReason, admin.getAdmin_id(), reportId);
        jdbc.update("UPDATE report_history SET valid_to = SYSDATE WHERE report_id = ? AND valid_to IS NULL", reportId);
        String changeType = "ACCEPTED".equals(request.statusCode) ? "APPROVE" : "REJECT";
        jdbc.update("""
                INSERT INTO report_history (
                    report_history_id, report_id, office_id, target_vehicle_id,
                    target_vehicle_number, parking_space_id, report_type_code, content,
                    status_code, reviewer_admin_id, review_reason, reviewed_at, created_at,
                    changed_by_admin_id, actor_type_code, actor_id, change_type_code,
                    change_reason, valid_from, valid_to
                )
                SELECT seq_report_history.NEXTVAL, r.report_id, r.office_id, r.target_vehicle_id,
                       r.target_vehicle_number, r.parking_space_id, r.report_type_code, r.content,
                       r.status_code, r.reviewer_admin_id, r.review_reason, r.reviewed_at, r.created_at,
                       ?, 'ADMIN', ?, ?, ?, SYSDATE, NULL
                FROM report r WHERE r.report_id = ?
                """, admin.getAdmin_id(), admin.getAdmin_id(), changeType, request.reviewReason, reportId);

        return Map.of("reportId", reportId, "statusCode", request.statusCode, "message", message);
    }

    private List<Map<String, Object>> normalizeRows(List<Map<String, Object>> rows) {
        return rows.stream().map(row -> {
            Map<String, Object> normalized = new LinkedHashMap<>();
            row.forEach((key, value) -> normalized.put(key.toLowerCase(Locale.ROOT), value));
            return normalized;
        }).toList();
    }

    private void insertUserNotification(Long officeId, String type, String title, String content, Long reportId) {
        jdbc.update("INSERT INTO notification (notification_id, office_id, notification_type_code, title, content, read_yn, created_at, report_id) VALUES (SEQ_NOTIFICATION.NEXTVAL, ?, ?, ?, ?, 'N', SYSDATE, ?)",
                officeId, type, title, content, reportId);
    }

    private Admin requireAdmin(Object principal) {
        if (!(principal instanceof Admin admin) || admin.getAdmin_id() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        return admin;
    }

    public static class ReviewRequest {
        public String statusCode;
        public String reviewReason;
        public String violationTypeCode;
        public Integer penaltyAmount;
        public Integer rewardAmount;
    }
}