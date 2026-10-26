package kr.co.alpharking.controller.report;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dto.report.ReportCreateRequest;
import kr.co.alpharking.entity.report.ReportEntity;
import kr.co.alpharking.repository.report.ReportRepository;
import kr.co.alpharking.security.Office;

@RestController
@RequestMapping("/api/reports")
public class ReportController {
	private final ReportRepository reportRepository;
	private final JdbcTemplate jdbc;

	public ReportController(ReportRepository reportRepository, JdbcTemplate jdbc) {
		this.reportRepository = reportRepository;
		this.jdbc = jdbc;
	}

	@PostMapping
	// 신고 저장과 이력 기록을 하나의 트랜잭션으로 묶어 부분 저장을 방지한다.
	@Transactional
	public ResponseEntity<Map<String, Object>> create(@RequestBody ReportCreateRequest request,
			@AuthenticationPrincipal Office office) {
		if (office == null || office.getOffice_id() == null) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다.");
		}
		if (request == null || request.getContent() == null || request.getContent().isBlank()
				|| request.getReportTypeCode() == null || request.getReportTypeCode().isBlank()
				|| request.getTargetVehicleNumber() == null || request.getTargetVehicleNumber().isBlank()) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "차량번호, 신고 유형, 신고 내용은 필수입니다.");
		}

		Map<String, Object> targetVehicle;
		try {
			targetVehicle = jdbc.queryForMap(
					"SELECT vehicle_id, office_id FROM vehicle WHERE vehicle_number = ? AND deleted_at IS NULL AND ROWNUM = 1",
					request.getTargetVehicleNumber().trim());
		} catch (org.springframework.dao.EmptyResultDataAccessException ex) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "등록된 신고 대상 차량을 찾을 수 없습니다.");
		}
		Long targetOfficeId = ((Number) targetVehicle.get("OFFICE_ID")).longValue();
		if (office.getOffice_id().equals(targetOfficeId)) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "본인 소속 차량은 신고할 수 없습니다.");
		}

		ReportEntity report = new ReportEntity();
		report.setOfficeId(office.getOffice_id());
		report.setTargetVehicleId(((Number) targetVehicle.get("VEHICLE_ID")).longValue());
		report.setTargetVehicleNumber(request.getTargetVehicleNumber().trim());
		report.setParkingSpaceId(request.getParkingSpaceId());
		report.setReportTypeCode(request.getReportTypeCode().trim());
		report.setContent(request.getContent().trim());
		report.setStatusCode("RECEIVED");
		ReportEntity saved = reportRepository.saveAndFlush(report);

		// 접수 당시 상태(RECEIVED)를 REPORT_HISTORY에 첫 이력 스냅샷으로 저장한다.
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
				       NULL, 'USER', ?, 'INSERT', '신고 접수', SYSDATE, NULL
				FROM report r WHERE r.report_id = ?
				""", office.getOffice_id(), saved.getReportId());

		return ResponseEntity.status(HttpStatus.CREATED)
				.body(Map.of("reportId", saved.getReportId(), "statusCode", saved.getStatusCode()));
	}
}