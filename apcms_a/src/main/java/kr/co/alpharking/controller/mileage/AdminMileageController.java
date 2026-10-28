package kr.co.alpharking.controller.mileage;

import java.math.BigDecimal;
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

    // 관리자 마일리지 조회·등록에 사용할 JDBC 실행 객체를 주입받는다.
    public AdminMileageController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping
    // 관리자 권한을 확인하고 최근 마일리지 이력 100건을 조회한다.
    public List<Map<String, Object>> list(@AuthenticationPrincipal Object principal) {
        // 인증 principal이 유효한 관리자 계정인지 검사한다.
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
    // 마일리지 지급·차감 대상 선택에 필요한 사무실 목록을 조회한다.
    public List<Map<String, Object>> offices(@AuthenticationPrincipal Object principal) {
        // 인증 principal이 유효한 관리자 계정인지 검사한다.
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
    // 관리자 권한·대상·금액을 검증하고 잠금과 잔액 검사를 거쳐 적립 또는 사용 이력을 저장한다.
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

        // by팀장: 같은 사무실의 적립·차감을 트랜잭션 종료까지 직렬화한다.
        // 사용자 관리비 차감도 잔액 조회 전에 동일한 OFFICE 행을 잠가야 한다.
        List<Long> offices = jdbc.queryForList(
                "SELECT office_id FROM office WHERE office_id = ? FOR UPDATE", Long.class, request.officeId);
        if (offices.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "선택한 사무실을 찾을 수 없습니다.");
        }

        if ("USE".equals(request.mileageTypeCode)) {
            // by팀장: 기존 화면과 동일하게 과거 양수 USE도 차감으로 계산하고 잔액 부족 시 저장하지 않는다.
            BigDecimal balance = jdbc.queryForObject("""
                    SELECT NVL(SUM(CASE WHEN mileage_type_code = 'USE'
                                        THEN -ABS(amount) ELSE amount END), 0)
                    FROM mileage_history
                    WHERE office_id = ?
                    """, BigDecimal.class, request.officeId);
            if (balance == null || balance.compareTo(BigDecimal.valueOf(request.amount)) < 0) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "사용 가능한 마일리지가 부족합니다.");
            }
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

    // 인증 principal이 유효한 관리자 계정인지 검사한다.
    private Admin requireAdmin(Object principal) {
        if (!(principal instanceof Admin admin) || admin.getAdmin_id() == null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
        return admin;
    }

    // Oracle 조회 결과의 컬럼 키를 프론트 응답용 소문자로 변환한다.
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
