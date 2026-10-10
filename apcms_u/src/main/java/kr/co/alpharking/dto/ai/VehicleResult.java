package kr.co.alpharking.dto.ai;

import com.fasterxml.jackson.annotation.JsonProperty;

import lombok.Data;

@Data
public class VehicleResult {

//	@JsonProperty : JSON의 "vehicle_index" -> Java의 vehicleIndex
//	FastAPI 에서의 json의 이름과 Java에서의 이름을 매핑시키는 역할
	@JsonProperty("vehicle_index")
	private int vehicleIndex;

	@JsonProperty("vehicle_type")
	private String vehicleType;

	@JsonProperty("vehicle_confidence")
	private double vehicleConfidence;

	@JsonProperty("plate_detected")
	private boolean plateDetected;

	@JsonProperty("plate_confidence")
	private Double plateConfidence;

	@JsonProperty("plate_number")
	private String plateNumber;

	@JsonProperty("plate_type")
	private String plateType;

	@JsonProperty("first_ocr")
	private String firstOcr;

	@JsonProperty("first_type")
	private String firstType;

	@JsonProperty("retry_ocr")
	private String retryOcr;

	@JsonProperty("retry_type")
	private String retryType;
}