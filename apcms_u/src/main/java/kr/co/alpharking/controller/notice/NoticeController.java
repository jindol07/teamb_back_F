
package kr.co.alpharking.controller.notice;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dto.notice.NoticeRes;
import kr.co.alpharking.entity.notice.NoticeAttachment;
import kr.co.alpharking.service.notice.NoticeService;

@RestController
@RequestMapping("/api/notice")
public class NoticeController {

	@Autowired
	private NoticeService noticeService;

	// 관리자와 공유하는 실제 첨부파일 저장 폴더
	@Value("${notice.upload-dir}")
	private String noticeUploadDir;

	// ========================================
	// 1. 사용자 공지사항 목록 및 검색
	// ========================================
	@GetMapping
	public ResponseEntity<List<NoticeRes>> getAllNotices(
			@RequestParam(name = "keyword", required = false) String keyword,
			@RequestParam(name = "type", required = false) String type) {

		List<NoticeRes> nList = noticeService.getAllNotices(keyword, type);

		return ResponseEntity.ok(nList);
	}

	// ========================================
	// 2. 사용자 공지사항 상세 조회
	// ========================================
	@GetMapping("/{noticeId}")
	public ResponseEntity<NoticeRes> getNoticeDetail(@PathVariable("noticeId") Integer noticeId) {

		NoticeRes notice = noticeService.getNoticeDetail(noticeId);

		return ResponseEntity.ok(notice);
	}

	// ========================================
	// 3. 사용자 공지사항 첨부파일 다운로드
	// ========================================
	@GetMapping("/{noticeId}/file/{attachmentId}/download")
	public ResponseEntity<Resource> downloadNoticeFile(@PathVariable("noticeId") Integer noticeId,
			@PathVariable("attachmentId") Integer attachmentId) {

		// DB에서 해당 공지사항의 첨부파일 조회
		NoticeAttachment attachment = noticeService.getNoticeAttachment(noticeId, attachmentId);

		// 관리자 파일 저장 폴더
		Path uploadDir = Paths.get(noticeUploadDir).toAbsolutePath().normalize();

		// DB에 저장된 실제 파일 경로
		String filePath = attachment.getFilePath();

		if (filePath == null || filePath.isBlank()) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "첨부파일 경로가 없습니다.");
		}

		Path path;

		try {
			path = Paths.get(filePath).toAbsolutePath().normalize();
			
//			System.out.println("===== 첨부파일 다운로드 디버깅 =====");
//			System.out.println("noticeId: " + noticeId);
//			System.out.println("attachmentId: " + attachmentId);
//			System.out.println("DB 파일 경로: " + filePath);
//			System.out.println("설정된 업로드 폴더: " + uploadDir);
//			System.out.println("검사 대상 절대 경로: " + path);
//			System.out.println("폴더 내부 여부: " + path.startsWith(uploadDir));
//			System.out.println("일반 파일 여부: " + Files.isRegularFile(path));
//			System.out.println("읽기 가능 여부: " + Files.isReadable(path));
//			System.out.println("====================================");

		} catch (RuntimeException e) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "첨부파일 경로가 올바르지 않습니다.", e);
		}

		// 허용된 폴더 내부의 파일인지 확인
		if (!path.startsWith(uploadDir) || !Files.isRegularFile(path) || !Files.isReadable(path)) {

			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "첨부파일을 찾을 수 없습니다.");
		}
		


		try {
			// 실제 파일을 Resource로 변환
			Resource resource = new UrlResource(path.toUri());

			// 원본 파일명으로 다운로드
			ContentDisposition disposition = ContentDisposition.attachment()
					.filename(attachment.getOriginalName(), StandardCharsets.UTF_8).build();

			return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM)
					.header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString()).body(resource);

		} catch (IOException e) {
			throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "첨부파일 다운로드 중 오류가 발생했습니다.", e);
		}
	}
}
