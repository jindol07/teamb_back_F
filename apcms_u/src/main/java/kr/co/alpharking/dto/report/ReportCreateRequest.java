package kr.co.alpharking.dto.report;

public class ReportCreateRequest {
	private String targetVehicleNumber;
	private Long targetVehicleId;
	private Long parkingSpaceId;
	private String reportTypeCode;
	private String content;

	public String getTargetVehicleNumber() { return targetVehicleNumber; }
	public void setTargetVehicleNumber(String value) { this.targetVehicleNumber = value; }
	public Long getTargetVehicleId() { return targetVehicleId; }
	public void setTargetVehicleId(Long value) { this.targetVehicleId = value; }
	public Long getParkingSpaceId() { return parkingSpaceId; }
	public void setParkingSpaceId(Long value) { this.parkingSpaceId = value; }
	public String getReportTypeCode() { return reportTypeCode; }
	public void setReportTypeCode(String value) { this.reportTypeCode = value; }
	public String getContent() { return content; }
	public void setContent(String value) { this.content = value; }
}
