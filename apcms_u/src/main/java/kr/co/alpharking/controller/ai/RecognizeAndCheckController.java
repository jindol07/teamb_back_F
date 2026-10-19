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

// 1. AI 인식 + 차량 조회 + 탐지 이벤트 저장 통합 처리
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class RecognizeAndCheckController {
	
	private final AiDetectionEventService aiDetectionEventService;
	
	@Autowired
	private AiRecognitionService aiRecognitionService;
	
	@Autowired
	private VehicleService vehicleService;
	
//	2. AI 번호판 인식 및 등록 승인 차량 확인
//  ex) http://192.168.0.23/alpharking/api/ai/recognizeAndCheck
	@PostMapping("/recognizeAndCheck")
	public ResponseEntity<AiVehicleCheckResponse> recognizeAndCheck(@RequestParam("file") MultipartFile file) throws IOException {
		
//		2-1. FastAPI에서 차량 인식 결과 가져오기
		AiRecognitionResponse aiResult = aiRecognitionService.recognize(file);
		
		AiVehicleCheckResponse response = new AiVehicleCheckResponse();
		
		response.setAiResult(aiResult);
		response.setRegistered(false);
		
//		2-2. 인식된 차량 목록 확인
		if (aiResult.getVehicles() != null && !aiResult.getVehicles().isEmpty()) {
			
			for (VehicleResult result : aiResult.getVehicles()) {
				
				String plateNumber = result.getPlateNumber();
				
				if (plateNumber != null && !plateNumber.isBlank()) {
					
					// 2-3. AI 탐지 이벤트 DB 저장
					aiDetectionEventService.saveDetectionEvent(result);
					
					// 2-4. 등록 승인 및 미삭제 차량 조회
					Optional<Vehicle> vehicle = vehicleService.findRegisteredVehicleByNumber(plateNumber);
					
					// 2-5. 승인된 등록 차량이면 정보 반환
					if (vehicle.isPresent()) {
						response.setRegistered(true);
						response.setVehicle(vehicle.get());
						break;
					}
				}
			}
		}
		// 2-6. 최종 결과 반환
		return ResponseEntity.ok(response);
	}
}