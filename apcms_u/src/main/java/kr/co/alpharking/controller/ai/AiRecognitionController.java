package kr.co.alpharking.controller.ai;

import java.io.IOException;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import kr.co.alpharking.dto.ai.AiRecognitionResponse;
import kr.co.alpharking.service.ai.AiRecognitionService;
import lombok.RequiredArgsConstructor;

// Spring Boot <-> FastAPI 연결만 단독으로 확인하는 용도
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class AiRecognitionController {

	private final AiRecognitionService aiRecognitionService;

//	http://192.168.0.23/alpharking/api/ai/recognize
	@PostMapping("/recognize")
	public ResponseEntity<AiRecognitionResponse> recognize(@RequestParam("file") MultipartFile file) throws IOException {
		AiRecognitionResponse result = aiRecognitionService.recognize(file);
		return ResponseEntity.ok(result);
	}
}