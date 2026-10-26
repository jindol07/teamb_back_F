
package kr.co.alpharking.entity.report;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.PrePersist;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;

import lombok.Getter;

@Entity
@Getter
@Table(name = "report")
@SequenceGenerator(name = "report_seq_generator", sequenceName = "SEQ_REPORT", allocationSize = 1)
public class ReportEntity {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "report_seq_generator")
	@Column(name = "report_id")
	private Long reportId; // 신고 식별자

	@Column(name = "office_id", nullable = false)
	private Long officeId; // 신고 office ID

	@Column(name = "target_vehicle_id")
	private Long targetVehicleId; // 대상 등록 차량 ID

	@Column(name = "target_vehicle_number", length = 50)
	private String targetVehicleNumber; // 신고 당시 차량번호

	@Column(name = "parking_space_id")
	private Long parkingSpaceId; // 대상 주차 공간 ID

	@Column(name = "review_reason", length = 500)
	private String reviewReason; // 검토 사유

	@Column(name = "report_type_code", length = 50, nullable = false)
	private String reportTypeCode; // ZONE_VIOLATION / ETC

	@Lob
	@Column(name = "content", nullable = false)
	private String content; // 신고 내용

	@Column(name = "status_code", length = 50, nullable = false)
	private String statusCode; // RECEIVED / ACCEPTED / REJECTED

	@Column(name = "reviewer_admin_id")
	private Long reviewerAdminId; // 검토 관리자 ID

	@Column(name = "reviewed_at")
	private LocalDateTime reviewedAt; // 검토 완료 일시

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt; // 신고 일시

	public ReportEntity() {
	}

	// 엔티티가 DB에 처음 저장되기 전에 실행
	@PrePersist
	protected void onCreate() {
		// 신고 일시가 설정되지 않았다면 현재 시각으로 자동 설정
		if (createdAt == null) {
			createdAt = LocalDateTime.now();
		}
	}

	public void setOfficeId(Long officeId) { this.officeId = officeId; }
	public void setTargetVehicleId(Long targetVehicleId) { this.targetVehicleId = targetVehicleId; }
	public void setTargetVehicleNumber(String targetVehicleNumber) { this.targetVehicleNumber = targetVehicleNumber; }
	public void setParkingSpaceId(Long parkingSpaceId) { this.parkingSpaceId = parkingSpaceId; }
	public void setReviewReason(String reviewReason) { this.reviewReason = reviewReason; }
	public void setReportTypeCode(String reportTypeCode) { this.reportTypeCode = reportTypeCode; }
	public void setContent(String content) { this.content = content; }
	public void setStatusCode(String statusCode) { this.statusCode = statusCode; }
	public void setReviewerAdminId(Long reviewerAdminId) { this.reviewerAdminId = reviewerAdminId; }
	public void setReviewedAt(LocalDateTime reviewedAt) { this.reviewedAt = reviewedAt; }
}
