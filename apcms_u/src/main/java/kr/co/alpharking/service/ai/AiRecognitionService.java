package kr.co.alpharking.service.ai;

import java.io.IOException;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;

import kr.co.alpharking.dto.ai.AiRecognitionResponse;

@Service
public class AiRecognitionService {
	
	private final RestClient restClient;
	
	// 1. FastAPI 서버 주소를 설정값으로 받아 RestClient 생성
	@Autowired
	public AiRecognitionService(@Value("${ai.vision.base-url}") String baseUrl) {
		this.restClient = RestClient.builder().baseUrl(baseUrl)
				.requestFactory(new SimpleClientHttpRequestFactory()).build();
	}
	
	// 2. FastAPI에 이미지 전송 후 차량 인식 결과 반환
	public AiRecognitionResponse recognize(MultipartFile file) throws IOException {
		
		ByteArrayResource resource = new ByteArrayResource(file.getBytes()) {
			@Override
			public String getFilename() {
				return file.getOriginalFilename();
			}
		};
		
		MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
		
		body.add("file", resource);
		
		return restClient.post().uri("/recognize")
				.contentType(MediaType.MULTIPART_FORM_DATA).body(body)
				.retrieve().body(AiRecognitionResponse.class);
	}
}