package kr.co.alpharking.dto.ai;

import kr.co.alpharking.entity.vehicle.Vehicle;
import lombok.Data;

// AI 인식 + 차량 조회 결과를 담는 DTO
@Data
public class AiVehicleCheckResponse {

	private AiRecognitionResponse aiResult;
	private boolean registered;
	private Vehicle vehicle;
}