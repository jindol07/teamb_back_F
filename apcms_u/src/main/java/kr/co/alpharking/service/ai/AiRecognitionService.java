package kr.co.alpharking.service.ai;

import java.io.IOException;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;

import kr.co.alpharking.dto.ai.AiRecognitionResponse;

@Service
public class AiRecognitionService {

	private final RestClient restClient;

	public AiRecognitionService() {

		this.restClient = RestClient.builder().baseUrl("http://127.0.0.1:8000").build();
	}

	public AiRecognitionResponse recognize(MultipartFile file) throws IOException {

		ByteArrayResource resource = new ByteArrayResource(file.getBytes()) {
			@Override
			public String getFilename() {
				return file.getOriginalFilename();
			}
		};

		MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();

		body.add("file", resource);

		return restClient.post().uri("/recognize").contentType(MediaType.MULTIPART_FORM_DATA).body(body).retrieve().body(AiRecognitionResponse.class);
	}
}