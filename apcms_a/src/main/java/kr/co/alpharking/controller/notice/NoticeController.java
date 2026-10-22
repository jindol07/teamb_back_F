
package kr.co.alpharking.controller.notice;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.dto.notice.NoticeFiles;
import kr.co.alpharking.dto.notice.NoticeHistory;
import kr.co.alpharking.service.notice.NoticeService;
import kr.co.alpharking.security.Admin;

@RestController
@RequestMapping("/api/notice")
public class NoticeController {

	@Autowired
	private NoticeService noticeService;

	// application.properties에 설정된 파일 저장 경로
	@Value("${spring.servlet.multipart.location}")
	private String filePath;

	// JWT 필터가 DB에서 조회한 관리자만 사용하며, 요청으로 받은 ID는 신뢰하지 않습니다.
	private Long getAuthenticatedAdminId(Authentication authentication) {
		if (authentication == null || !authentication.isAuthenticated()) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
		}
		if (!(authentication.getPrincipal() instanceof Admin admin) || admin.getAdmin_id() == null
				|| authentication.getAuthorities().stream().noneMatch(role -> "ADMIN".equals(role.getAuthority()))) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
		}
		return admin.getAdmin_id();
	}

	// ========================================
	// 1. 공지사항 등록 + 첨부파일 등록
	// ========================================
	@PostMapping("/add")
	public ResponseEntity<?> addNotice(NoticeCreateReq galleryVO,
			@RequestParam(value = "files", required = false) MultipartFile[] images, Authentication authentication) {

		// 파일 저장 전에 인증을 확인하고, 프론트가 보낸 작성자 ID도 덮어씁니다.
		galleryVO.setWriterAdminId(Math.toIntExact(getAuthenticatedAdminId(authentication)));

		// 첨부파일 정보를 저장할 목록
		List<NoticeFiles> imageList = new ArrayList<>();

		// DB 등록 실패 시 저장된 파일을 정리하기 위한 목록
		List<Path> savedPaths = new ArrayList<>();

		try {

			// 파일 저장 폴더 생성
			Path uploadDir = Paths.get(filePath, "notice").toAbsolutePath().normalize();

			Files.createDirectories(uploadDir);

			// 첨부파일이 있을 경우 처리
			if (images != null) {

				for (MultipartFile file : images) {

					if (file.isEmpty()) {
						continue;
					}

					// 원본 파일명 가져오기
					String originalFilename = file.getOriginalFilename();

					if (originalFilename == null || originalFilename.isBlank()) {

						throw new IllegalArgumentException("파일명이 올바르지 않습니다.");
					}

					// 경로 문자열 제거
					originalFilename = originalFilename.replace("\\", "/");

					originalFilename = originalFilename.substring(originalFilename.lastIndexOf("/") + 1);

					// 원본 파일명 길이 검사
					if (originalFilename.isBlank() || originalFilename.length() > 100) {

						throw new IllegalArgumentException("파일명은 100자 이하여야 합니다.");
					}

					// UUID 기반 저장 파일명 생성
					String storedName = UUID.randomUUID().toString() + "_" + originalFilename;

					// 저장 파일명 길이 검사
					if (storedName.length() > 100) {

						throw new IllegalArgumentException("저장 파일명이 100자를 초과합니다.");
					}

					// 실제 파일 저장 경로
					Path savePath = uploadDir.resolve(storedName).normalize();

					// 파일 크기 확인
					int fileSize = Math.toIntExact(file.getSize());

					// 실제 파일 저장
					file.transferTo(savePath);
					savedPaths.add(savePath);

					// 첨부파일 DTO 생성
					NoticeFiles imageVO = new NoticeFiles();

					imageVO.setOriginalName(originalFilename);
					imageVO.setStoredName(storedName);
					imageVO.setFilePath(savePath.toString());
					imageVO.setFileSize(fileSize);

					// 첨부파일 목록에 추가
					imageList.add(imageVO);
				}
			}

			// 공지사항 DTO에 첨부파일 목록 설정
			galleryVO.setGetfilelist(imageList);

			// 공지사항 + 첨부파일 DB 등록
			noticeService.transcationProcess(galleryVO, imageList);

			return ResponseEntity.ok("공지사항 등록(파일포함) 성공!");

		} catch (Exception e) {

			e.printStackTrace();

			// 등록 실패 시 저장한 파일 정리
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

	// ========================================
	// 2. 공지사항 목록 조회
	// ========================================
	@GetMapping
	public ResponseEntity<List<NoticeCreateReq>> getNoticeList() {

		List<NoticeCreateReq> noticeList = noticeService.getNoticeList();

		return ResponseEntity.ok(noticeList);
	}

	// ========================================
	// 3. 공지사항 상세 조회
	// ========================================
	@GetMapping("/{noticeId}")
	public ResponseEntity<NoticeCreateReq> getNoticeDetail(@PathVariable("noticeId") Integer noticeId) {

		// 해당 공지사항 조회
		NoticeCreateReq notice = noticeService.getNoticeDetail(noticeId);

		// 공지사항이 없으면 404 반환
		if (notice == null) {
			return ResponseEntity.notFound().build();
		}

		// 공지사항 및 첨부파일 목록 반환
		return ResponseEntity.ok(notice);
	}

	// ========================================
	// 4. 공지사항 수정 + 수정 이력 저장
	// ========================================
	@PutMapping("/{noticeId}")
	public ResponseEntity<?> updateNotice(@PathVariable("noticeId") Integer noticeId,
			@RequestBody NoticeCreateReq nidto, Authentication authentication) {

		Long changedByAdminId = getAuthenticatedAdminId(authentication);

		// URL의 공지사항 번호 설정
		nidto.setNoticeId(noticeId);

		// 공지사항 수정 및 이력 저장
		boolean result = noticeService.updateNotice(nidto, changedByAdminId);

		// 해당 공지사항이 없으면 404 반환
		if (!result) {
			return ResponseEntity.notFound().build();
		}

		return ResponseEntity.ok("공지사항 수정 및 이력 저장 성공!");
	}

	// ========================================
	// 5. 공지사항 소프트 삭제 + 삭제 이력 저장
	// ========================================
	@DeleteMapping("/{noticeId}")
	public ResponseEntity<?> deleteNotice(@PathVariable("noticeId") Integer noticeId,
			Authentication authentication) {

		Long changedByAdminId = getAuthenticatedAdminId(authentication);

		// 공지사항 삭제 및 이력 저장
		boolean result = noticeService.deleteNotice(noticeId, changedByAdminId);

		// 해당 공지사항이 없으면 404 반환
		if (!result) {
			return ResponseEntity.notFound().build();
		}

		return ResponseEntity.ok("공지사항 삭제 및 이력 저장 성공!");
	}

	// ========================================
	// 6. 공지사항 변경 이력 조회
	// ========================================
	@GetMapping("/{noticeId}/history")
	public ResponseEntity<List<NoticeHistory>> getNoticeHistoryList(@PathVariable("noticeId") Integer noticeId,
			Authentication authentication) {

		// 보안 필터뿐 아니라 실제 이력 조회 직전에도 인증된 관리자인지 확인합니다.
		getAuthenticatedAdminId(authentication);

		// NOTICE_HISTORY 테이블에서 이력 조회
		List<NoticeHistory> historyList = noticeService.getNoticeHistoryList(noticeId);

		// 변경 이력 목록 반환
		return ResponseEntity.ok(historyList);
	}

	// ========================================
	// 7. 공지사항 첨부파일 다운로드 (관리자)
	// ========================================
	@GetMapping("/{noticeId}/file/download")
	public ResponseEntity<Resource> downloadNoticeFile(@PathVariable("noticeId") Integer noticeId) {

		// 삭제되지 않은 공지사항인지 확인
		NoticeCreateReq notice = noticeService.getNoticeDetail(noticeId);

		if (notice == null) {
			return ResponseEntity.notFound().build();
		}

		// 공지사항에 등록된 첨부파일 조회
		List<NoticeFiles> files = notice.getGetfilelist();

		if (files == null || files.isEmpty()) {
			return ResponseEntity.notFound().build();
		}

		// 첨부파일 1개 기준
		NoticeFiles file = files.get(0);

		try {

			// 서버에 저장된 파일 확인
			Path uploadDir = Paths.get(filePath, "notice").toAbsolutePath().normalize();

			Path path = Paths.get(file.getFilePath()).toAbsolutePath().normalize();

			// 지정된 업로드 폴더 밖의 파일 접근 방지
			if (/*!path.startsWith(uploadDir) ||*/ !Files.isRegularFile(path) || !Files.isReadable(path)) {
				return ResponseEntity.notFound().build();
			}

			Resource resource = new UrlResource(path.toUri());

			// 원본 파일명으로 다운로드
			String originalName = file.getOriginalName();

			ContentDisposition disposition = ContentDisposition.attachment()
					.filename(originalName, StandardCharsets.UTF_8).build();

			return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM)
					.header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString()).body(resource);

		} catch (Exception e) {

			e.printStackTrace();

			return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
		}
	}
}
