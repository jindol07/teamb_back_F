
package kr.co.alpharking.service.notice;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dto.notice.NoticeRes;
import kr.co.alpharking.entity.notice.Notice;
import kr.co.alpharking.repository.notice.NoticeRepository;
import kr.co.alpharking.entity.notice.NoticeAttachment;
import kr.co.alpharking.repository.notice.NoticeAttachmentRepository;

@Service
public class NoticeService {

	@Autowired
	private NoticeRepository noticeRepository;
	@Autowired
	private NoticeAttachmentRepository noticeAttachmentRepository;

	// 사용자 공지사항 목록 조회 + 제목 검색 + 유형 필터
	public List<NoticeRes> getAllNotices(String keyword, String type) {
		// 검색어가 비어 있으면 전체 조회
		if (keyword != null && keyword.trim().isEmpty()) {
			keyword = null;
		}
		// 유형이 전체이거나 비어 있으면 전체 유형 조회
		if (type != null && (type.trim().isEmpty() || type.equalsIgnoreCase("ALL"))) {
			type = null;
		}
		// JPA Repository에서 조건에 맞는 공지사항 조회
		return noticeRepository.searchNotices(keyword, type).stream().map(NoticeRes::from).toList();
	}

	// 사용자 공지사항 상세 조회 + 조회수 증가
	@Transactional
	public NoticeRes getNoticeDetail(Integer noticeId) {

		// 1. 공지사항 번호로 조회 (삭제된 공지사항 제외)
		Notice notice = noticeRepository.findByNoticeIdAndDeletedAtIsNull(noticeId)
				.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "공지사항을 찾을 수 없습니다."));

		// 2. 조회수 1 증가
		int updatedCount = noticeRepository.increaseViewCount(noticeId);

		if (updatedCount != 1) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "공지사항을 찾을 수 없습니다.");
		}

		// 3. 응답 데이터에 증가된 조회수 반영
		notice.setViewCount(notice.getViewCount() + 1);

		// 4. Entity를 DTO로 변환하여 반환
		return NoticeRes.from(notice);
	}

	// 사용자 공지사항 첨부파일 조회
	@Transactional(readOnly = true)
	public NoticeAttachment getNoticeAttachment(Integer noticeId, Integer attachmentId) {

		// 삭제되지 않은 공지사항인지 확인
		if (noticeRepository.findByNoticeIdAndDeletedAtIsNull(noticeId).isEmpty()) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "공지사항을 찾을 수 없습니다.");
		}

		// 해당 공지사항에 속한 첨부파일 조회
		return noticeAttachmentRepository.findByNoticeAttachmentIdAndNotice_NoticeId(attachmentId, noticeId)
				.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "첨부파일을 찾을 수 없습니다."));
	}

}
