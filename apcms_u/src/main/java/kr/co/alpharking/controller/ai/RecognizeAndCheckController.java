package kr.co.alpharking.controller.ai;

import java.io.IOException;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import kr.co.alpharking.dto.ai.AiRecognitionResponse;
import kr.co.alpharking.dto.ai.AiVehicleCheckResponse;
import kr.co.alpharking.dto.ai.VehicleResult;
import kr.co.alpharking.entity.vehicle.Vehicle;
import kr.co.alpharking.service.ai.AiDetectionEventService;
import kr.co.alpharking.service.ai.AiRecognitionService;
import kr.co.alpharking.service.vehicle.VehicleService;
import lombok.RequiredArgsConstructor;

// AI 인식 + 차량 조회 + 탐지 이벤트 저장 통합 처리 Controller
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class RecognizeAndCheckController {

	private final AiDetectionEventService aiDetectionEventService;

	@Autowired
	private AiRecognitionService aiRecognitionService;

	@Autowired
	private VehicleService vehicleService;

//	http://192.168.0.23/alpharking/api/ai/recognizeAndCheck
	@PostMapping("/recognizeAndCheck")
	public ResponseEntity<AiVehicleCheckResponse> recognizeAndCheck(@RequestParam("file") MultipartFile file)
			throws IOException {

		AiRecognitionResponse aiResult = aiRecognitionService.recognize(file);

		AiVehicleCheckResponse response = new AiVehicleCheckResponse();

		response.setAiResult(aiResult);
		response.setRegistered(false);

		if (aiResult.getVehicles() != null && !aiResult.getVehicles().isEmpty()) {

			for (VehicleResult result : aiResult.getVehicles()) {

				String plateNumber = result.getPlateNumber();

				if (plateNumber != null && !plateNumber.isBlank()) {

					aiDetectionEventService.saveDetectionEvent(result);

					Optional<Vehicle> vehicle = vehicleService.findByVehicleNumber(plateNumber);

					if (vehicle.isPresent()) {
						response.setRegistered(true);
						response.setVehicle(vehicle.get());
						break;
					}
				}
			}
		}

		return ResponseEntity.ok(response);
	}
}
