package kr.co.alpharking.controller.mileage;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.security.Admin;

/* 관리자가 사무실을 선택해 마일리지를 등록하고 이력을 조회하는 API. */
@RestController
@RequestMapping("/api/mileage")
public class AdminMileageController {
    private final JdbcTemplate jdbc;

    public AdminMileageController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping
    public List<Map<String, Object>> list(@AuthenticationPrincipal Object principal) {
        requireAdmin(principal);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT * FROM (
                    SELECT m.mileage_history_id AS mileagehistoryid,
                           m.mileage_type_code AS mileagetypecode,
                           m.amount,
                           m.reference_type_code AS referencetypecode,
                           m.reference_id AS referenceid,
                           m.description,
                           m.created_at AS createdat,
                           o.office_id AS officeid,
                           o.office_number AS officenumber
                    FROM mileage_history m
                    LEFT JOIN office o ON o.office_id = m.office_id
                    ORDER BY m.created_at DESC, m.mileage_history_id DESC
                ) WHERE ROWNUM <= 100
                """);
        return normalizeRows(rows);
    }

    @GetMapping("/offices")
    public List<Map<String, Object>> offices(@AuthenticationPrincipal Object principal) {
        requireAdmin(principal);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT office_id AS officeid, office_number AS officenumber
                FROM office
                ORDER BY office_number
                """);
        return normalizeRows(rows);
    }

    @PostMapping
    @Transactional
    public Map<String, Object> create(@RequestBody MileageCreateRequest request,
                                     @AuthenticationPrincipal Object principal) {
        Admin admin = requireAdmin(principal);
        if (request == null || request.officeId == null || request.officeId <= 0
                || request.amount == null || request.amount <= 0
                || request.mileageTypeCode == null
                || !("ADMIN_REWARD".equals(request.mileageTypeCode) || "USE".equals(request.mileageTypeCode)
                        || "ON_TIME_EXIT_REWARD".equals(request.mileageTypeCode))
                || request.description == null || request.description.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "사무실, 유형, 양수 마일리지, 처리 사유를 확인해 주세요.");
        }

        Integer officeCount = jdbc.queryForObject(
                "SELECT COUNT(*) FROM office WHERE office_id = ?", Integer.class, request.officeId);
        if (officeCount == null || officeCount == 0) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "선택한 사무실을 찾을 수 없습니다.");
        }

        long storedAmount = "USE".equals(request.mileageTypeCode)
                ? -Math.abs(request.amount) : Math.abs(request.amount);
        jdbc.update("""
                INSERT INTO mileage_history (
                    mileage_history_id, mileage_type_code, amount,
                    reference_type_code, reference_id, description, created_at, office_id
                ) VALUES (
                    SEQ_MILEAGE_HISTORY.NEXTVAL, ?, ?, 'ADMIN', ?, ?, SYSDATE, ?
                )
                """, request.mileageTypeCode, storedAmount, admin.getAdmin_id(),
                request.description.trim(), request.officeId);

        Long historyId = jdbc.queryForObject("SELECT SEQ_MILEAGE_HISTORY.CURRVAL FROM dual", Long.class);
        return Map.of(
                "mileagehistoryid", historyId,
                "mileagetypecode", request.mileageTypeCode,
                "amount", storedAmount,
                "description", request.description.trim(),
                "officeid", request.officeId);
    }

    private Admin requireAdmin(Object principal) {
        if (!(principal instanceof Admin admin) || admin.getAdmin_id() == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
        return admin;
    }

    private List<Map<String, Object>> normalizeRows(List<Map<String, Object>> rows) {
        return rows.stream().map(row -> {
            Map<String, Object> normalized = new LinkedHashMap<>();
            row.forEach((key, value) -> normalized.put(key.toLowerCase(Locale.ROOT), value));
            return normalized;
        }).toList();
    }

    public static class MileageCreateRequest {
        public Long officeId;
        public String mileageTypeCode;
        public Long amount;
        public String description;
    }
}