
package kr.co.alpharking.controller.notice;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.dto.notice.NoticeFiles;
import kr.co.alpharking.service.notice.NoticeService;

@RestController
@RequestMapping("/api/notice")
public class NoticeController {

	@Autowired
	private NoticeService noticeService;

	@Value("${spring.servlet.multipart.location}")
	private String filePath;

	@PostMapping("/add")
	public ResponseEntity<?> addNotice(NoticeCreateReq galleryVO,
			@RequestParam(value = "files", required = false) MultipartFile[] images) {

		// 1. 첨부파일 정보를 저장할 목록
		List<NoticeFiles> imageList = new ArrayList<>();

		// DB 등록 실패 시 저장된 파일을 정리하기 위한 목록
		List<Path> savedPaths = new ArrayList<>();

		try {
			// 2. 파일 저장 폴더 생성
			Path uploadDir = Paths.get(filePath, "notice").toAbsolutePath().normalize();

			Files.createDirectories(uploadDir);

			// 3. 첨부파일이 있을 경우 처리
			if (images != null) {

				for (MultipartFile file : images) {

					if (file.isEmpty()) {
						continue;
					}

					// 4. 원본 파일명 가져오기
					String originalFilename = file.getOriginalFilename();

					if (originalFilename == null || originalFilename.isBlank()) {
						throw new IllegalArgumentException("파일명이 올바르지 않습니다.");
					}

					// 경로 문자열 제거
					originalFilename = originalFilename.replace("\\", "/");

					originalFilename = originalFilename.substring(originalFilename.lastIndexOf("/") + 1);

					if (originalFilename.isBlank() || originalFilename.length() > 100) {
						throw new IllegalArgumentException("파일명은 100자 이하여야 합니다.");
					}

					// 5. 서버 저장 파일명 생성
					String storedName = UUID.randomUUID().toString() + "_" + originalFilename;

					if (storedName.length() > 100) {
						throw new IllegalArgumentException("저장 파일명이 100자를 초과합니다.");
					}

					// 6. 저장 경로 생성
					Path savePath = uploadDir.resolve(storedName).normalize();

					// 파일 크기 확인
					int fileSize = Math.toIntExact(file.getSize());

					// 7. 실제 파일 저장
					file.transferTo(savePath);
					savedPaths.add(savePath);

					// 8. 첨부파일 DTO 생성
					NoticeFiles imageVO = new NoticeFiles();
					
					imageVO.setOriginalName(originalFilename);
					imageVO.setStoredName(storedName);
					imageVO.setFilePath(savePath.toString());
					imageVO.setFileSize(fileSize);

					// 9. 목록에 추가
					imageList.add(imageVO);
				}
			}

			// 10. 기존 팀장님 코드 유지
			galleryVO.setGetfilelist(imageList);

			// 11. 공지사항 + 첨부파일 DB 등록
			noticeService.transcationProcess(galleryVO, imageList);

			return ResponseEntity.ok("공지사항 등록(파일포함) 성공!");

		} catch (Exception e) {

			e.printStackTrace();

			// 실패 시 이번 요청에서 저장한 파일 정리
			for (Path savedPath : savedPaths) {
				try {
					Files.deleteIfExists(savedPath);
				} catch (IOException cleanupError) {
					cleanupError.printStackTrace();
				}
			}

			if (e instanceof IllegalArgumentException || e instanceof ArithmeticException) {
				return ResponseEntity.badRequest().body("첨부파일 정보가 올바르지 않습니다.");
			}

			return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body("공지사항 등록(파일포함) 실패...");
		}
	}
}
