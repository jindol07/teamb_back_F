package kr.co.alpharking.service.ai;

import java.time.LocalDateTime;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import kr.co.alpharking.dto.ai.VehicleResult;
import kr.co.alpharking.entity.ai.AiDetectionEvent;
import kr.co.alpharking.repository.ai.AiDetectionEventRepository;
import tools.jackson.databind.ObjectMapper;

@Service
public class AiDetectionEventService {

	@Autowired
	private AiDetectionEventRepository aiDetectionEventRepository;

	@Autowired
	private ObjectMapper objectMapper;

	public AiDetectionEvent saveDetectionEvent(VehicleResult result) {

		AiDetectionEvent event = new AiDetectionEvent();

		event.setDetectedVehicleNumber(result.getPlateNumber());

		event.setDetectedAt(LocalDateTime.now());

		event.setCreatedAt(LocalDateTime.now());

//		자바 객체 VehicleResult를 JSON 문자열로 바꿔줌
		String rawPayload = objectMapper.writeValueAsString(result);

//		바꾼 JSON 문자열을 db(RAW_PAYLOAD컬럼)에 저장
		event.setRawPayload(rawPayload);

		return aiDetectionEventRepository.save(event);
	}
}