package kr.co.alpharking.dto.ai;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

import lombok.Data;

@Data
public class AiRecognitionResponse {

	private boolean success;

	private String message;

	@JsonProperty("vehicle_fallback_used")
	private boolean vehicleFallbackUsed;

	@JsonProperty("vehicle_count")
	private int vehicleCount;

	private List<VehicleResult> vehicles;
}