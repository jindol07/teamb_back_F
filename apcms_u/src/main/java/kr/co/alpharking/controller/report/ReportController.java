package kr.co.alpharking.controller.report;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
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
	public ResponseEntity<Map<String, Object>> create(
			@RequestBody ReportCreateRequest request,
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
			targetVehicle = jdbc.queryForMap("SELECT vehicle_id, office_id FROM vehicle WHERE vehicle_number = ? AND deleted_at IS NULL AND ROWNUM = 1", request.getTargetVehicleNumber().trim());
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
		ReportEntity saved = reportRepository.save(report);
		return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
				"reportId", saved.getReportId(), "statusCode", saved.getStatusCode()));
	}
}
