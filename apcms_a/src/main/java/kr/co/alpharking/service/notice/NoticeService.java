
package kr.co.alpharking.service.notice;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.dao.notice.NoticeDao;
import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.dto.notice.NoticeFiles;
import kr.co.alpharking.dto.notice.NoticeHistory;

@Service
public class NoticeService {

	@Autowired
	private NoticeDao noticeDao;

	// 공지사항 등록 및 첨부파일 등록 + INSERT 이력 저장
	@Transactional
	public void transcationProcess(NoticeCreateReq nidto, List<NoticeFiles> nfvo) {

		// 1. 공지사항 등록
		noticeDao.add(nidto);

		// 2. 등록된 공지사항 정보 다시 조회
		// DB에서 생성된 ID, CREATED_AT, UPDATED_AT 확보
		NoticeCreateReq savedNotice = noticeDao.findById(nidto.getNoticeId());

		if (savedNotice == null) {
			throw new IllegalStateException("등록된 공지사항을 조회할 수 없습니다.");
		}

		// 3. 등록 관리자 번호
		Long adminId = savedNotice.getWriterAdminId().longValue();

		// 4. 공지사항 INSERT 이력 생성
		NoticeHistory insertHistory = createNoticeHistory(savedNotice, adminId, "INSERT", "공지사항 신규 등록",
				savedNotice.getCreatedAt());

		// 신규 등록은 현재 버전이므로 종료 시각 없음
		insertHistory.setValidTo(null);

		// 5. 공지사항 INSERT 이력 저장
		noticeDao.insertNoticeHistory(insertHistory);

		// 6. 첨부파일이 있는 경우에만 등록
		if (nfvo != null && !nfvo.isEmpty()) {

			// 첨부파일은 1개만 허용
			if (nfvo.size() > 1) {
				throw new IllegalArgumentException("첨부파일은 1개만 등록할 수 있습니다.");
			}

			NoticeFiles file = nfvo.get(0);

			// 7. 첨부파일 번호 설정
			file.setNoticeId(savedNotice.getNoticeId());
			file.setNoticeAttachmentId(noticeDao.nextAttachmentId());

			// 8. 첨부파일 DB 등록
			noticeDao.addfile(List.of(file));

			// 9. 첨부파일 FILE_ADD 이력 생성
			NoticeHistory fileHistory = createNoticeHistory(savedNotice, adminId, "FILE_ADD", "공지사항 첨부파일 신규 등록",
					noticeDao.getCurrentDateTime());

			// 10. 신규 첨부파일 정보 저장
			fileHistory.setNoticeAttachmentId(file.getNoticeAttachmentId());
			fileHistory.setOriginalName(file.getOriginalName());
			fileHistory.setStoredName(file.getStoredName());
			fileHistory.setFilePath(file.getFilePath());
			fileHistory.setFileSize(file.getFileSize());

			fileHistory.setValidTo(null);

			// 11. 첨부파일 FILE_ADD 이력 저장
			noticeDao.insertNoticeHistory(fileHistory);
		}
	}

	// 공지사항 목록 조회
	public List<NoticeCreateReq> getNoticeList() {

		return noticeDao.findAll();
	}

	// 공지사항 상세 조회 및 첨부파일 조회
	public NoticeCreateReq getNoticeDetail(Integer noticeId) {

		// 1. 공지사항 정보 조회
		NoticeCreateReq notice = noticeDao.findById(noticeId);

		// 2. 공지사항이 없으면 null 반환
		if (notice == null) {
			return null;
		}

		// 3. 해당 공지사항의 첨부파일 조회
		List<NoticeFiles> files = noticeDao.findFilesByNoticeId(noticeId);

		// 4. 공지사항 DTO에 첨부파일 목록 저장
		notice.setGetfilelist(files);

		// 5. 공지사항 정보와 첨부파일 목록 반환
		return notice;
	}

	/**
	 * 공지사항 수정 및 버전 유효 기간 관리
	 */
	@Transactional
	public boolean updateNotice(NoticeCreateReq nidto, Long changedByAdminId) {

		// 1. 수정 전 공지사항 조회
		NoticeCreateReq oldNotice = noticeDao.findById(nidto.getNoticeId());

		if (oldNotice == null) {
			return false;
		}

		// 2. 변경 관리자 번호 확인
		if (changedByAdminId == null) {
			throw new IllegalArgumentException("변경 관리자 번호가 필요합니다.");
		}

		// 3. DB 현재 시각 조회
		String changedAt = noticeDao.getCurrentDateTime();

		// 4. 기존에 유효한 버전 종료
		int closedCount = noticeDao.closeCurrentNoticeHistory(nidto.getNoticeId(), changedAt);

		if (closedCount != 1) {
			throw new IllegalStateException("현재 유효한 공지사항 버전이 정확히 1건이어야 합니다.");
		}

		// 5. NOTICE 테이블 수정
		int result = noticeDao.updateNotice(nidto, changedAt);

		if (result != 1) {
			throw new IllegalStateException("공지사항 수정에 실패했습니다.");
		}

		// 6. 수정된 공지사항 다시 조회
		NoticeCreateReq updatedNotice = noticeDao.findById(nidto.getNoticeId());

		if (updatedNotice == null) {
			throw new IllegalStateException("수정된 공지사항을 조회할 수 없습니다.");
		}

		// 7. 수정 후 데이터로 새 버전 이력 생성
		NoticeHistory history = createNoticeHistory(updatedNotice, changedByAdminId, "UPDATE", "공지사항 수정", changedAt);

		// 8. 새 버전의 유효 시작 시각
		history.setValidFrom(changedAt);

		// 9. 새 버전은 아직 유효하므로 종료 시각 없음
		history.setValidTo(null);

		// 10. 새 버전 이력 저장
		noticeDao.insertNoticeHistory(history);

		return true;
	}

	/**
	 * 공지사항 소프트 삭제 및 버전 유효 기간 관리
	 */
	@Transactional
	public boolean deleteNotice(Integer noticeId, Long changedByAdminId) {

		// 1. 삭제 전 공지사항 조회
		NoticeCreateReq oldNotice = noticeDao.findById(noticeId);

		if (oldNotice == null) {
			return false;
		}

		// 2. 변경 관리자 번호 확인
		if (changedByAdminId == null) {
			throw new IllegalArgumentException("변경 관리자 번호가 필요합니다.");
		}

		// 3. DB 현재 시각 조회
		String changedAt = noticeDao.getCurrentDateTime();

		// 4. 기존에 유효한 공지사항 버전 종료
		int closedCount = noticeDao.closeCurrentNoticeHistory(noticeId, changedAt);

		if (closedCount != 1) {
			throw new IllegalStateException("현재 유효한 공지사항 버전이 정확히 1건이어야 합니다.");
		}

		// 5. NOTICE 테이블 소프트 삭제
		int result = noticeDao.deleteNotice(noticeId, changedAt);

		if (result != 1) {
			throw new IllegalStateException("공지사항 삭제에 실패했습니다.");
		}

		// 6. 삭제 전 데이터를 기반으로 DELETE 이벤트 이력 생성
		NoticeHistory history = createNoticeHistory(oldNotice, changedByAdminId, "DELETE", "공지사항 삭제", changedAt);

		// 7. 삭제 이벤트 발생 시각
		history.setValidFrom(changedAt);
		history.setValidTo(changedAt);

		// 8. 소프트 삭제 시각 기록
		history.setDeletedAt(changedAt);
		history.setUpdatedAt(changedAt);

		// 9. DELETE 이력 저장
		noticeDao.insertNoticeHistory(history);

		return true;
	}

	// 특정 공지사항의 변경 이력 목록 조회
	public List<NoticeHistory> getNoticeHistoryList(Integer noticeId) {

		return noticeDao.findNoticeHistoryByNoticeId(noticeId);
	}

	// 수정 및 삭제 전 공지사항 데이터를 이력 객체로 변환
	private NoticeHistory createNoticeHistory(NoticeCreateReq notice, Long changedByAdminId, String changeTypeCode,
			String changeReason, String changedAt) {

		NoticeHistory history = new NoticeHistory();

		// 1. 변경 전 공지사항 정보
		history.setNoticeId(notice.getNoticeId().longValue());
		history.setWriterAdminId(notice.getWriterAdminId().longValue());
		history.setNoticeTypeCode(notice.getNoticeTypeCode());
		history.setTitle(notice.getTitle());
		history.setContent(notice.getContent());
		history.setViewCount(notice.getViewCount());

		// 2. 기존 날짜 정보
		history.setCreatedAt(notice.getCreatedAt());
		history.setUpdatedAt(notice.getUpdatedAt());
		history.setDeletedAt(notice.getDeletedAt());

		// 3. 중요 공지 및 상단 고정 여부
		history.setImportantYn(notice.getImportantYn());
		history.setPinnedYn(notice.getPinnedYn());

		// 4. 변경한 관리자 정보
		history.setChangedByAdminId(changedByAdminId);
		history.setActorTypeCode("ADMIN");
		history.setActorId(changedByAdminId);

		// 5. 변경 유형 및 사유
		history.setChangeTypeCode(changeTypeCode);
		history.setChangeReason(changeReason);

		// 6. 기존 버전의 유효 시작 시각
		history.setValidFrom(notice.getUpdatedAt() != null ? notice.getUpdatedAt() : notice.getCreatedAt());

		// 7. 기존 버전의 유효 종료 시각
		history.setValidTo(changedAt);

		return history;
	}

	/**
	 * 공지사항 첨부파일 교체 또는 신규 등록
	 *
	 * @param noticeId 공지사항 번호
	 * @param newFile  새 첨부파일 정보
	 * @return 기존 공지사항이 존재하면 true, 없으면 false
	 */

	/**
	 * 공지사항 첨부파일 교체 또는 신규 등록 교체 전 첨부파일 정보를 NOTICE_HISTORY에 저장
	 */
	@Transactional
	public boolean replaceNoticeFile(Integer noticeId, NoticeFiles newFile, Long changedByAdminId) {

		// 1. 삭제되지 않은 공지사항인지 확인
		NoticeCreateReq notice = noticeDao.findById(noticeId);

		if (notice == null) {
			return false;
		}

		// 2. 변경 관리자 번호 확인
		if (changedByAdminId == null) {
			throw new IllegalArgumentException("변경 관리자 번호가 필요합니다.");
		}

		// 3. 기존 첨부파일 조회
		List<NoticeFiles> existingFiles = noticeDao.findFilesByNoticeId(noticeId);

		// 4. 새 첨부파일에 공지사항 번호 설정
		newFile.setNoticeId(noticeId);

		// 5. DB 현재 시각 조회
		String changedAt = noticeDao.getCurrentDateTime();

		if (existingFiles != null && !existingFiles.isEmpty()) {

			// 6. 기존 첨부파일 정보 가져오기
			NoticeFiles oldFile = existingFiles.get(0);

			// 7. 교체 전 공지사항 정보로 이력 생성
			NoticeHistory history = createNoticeHistory(notice, changedByAdminId, "FILE_REPLACE", "공지사항 첨부파일 교체",
					changedAt);

			// 8. 교체 전 첨부파일 정보 저장
			history.setNoticeAttachmentId(oldFile.getNoticeAttachmentId());
			history.setOriginalName(oldFile.getOriginalName());
			history.setStoredName(oldFile.getStoredName());
			history.setFilePath(oldFile.getFilePath());
			history.setFileSize(oldFile.getFileSize());

			// 9. NOTICE_HISTORY에 교체 전 이력 저장
			noticeDao.insertNoticeHistory(history);

			// 10. 기존 첨부파일 ID 유지
			newFile.setNoticeAttachmentId(oldFile.getNoticeAttachmentId());

			// 11. NOTICE_ATTACHMENT 정보 수정
			int result = noticeDao.updateNoticeFile(newFile);

			if (result != 1) {
				throw new IllegalStateException("첨부파일 정보 수정에 실패했습니다.");
			}

		} else {

			// 12. 기존 첨부파일이 없으면 신규 등록
			newFile.setNoticeAttachmentId(noticeDao.nextAttachmentId());

			noticeDao.addfile(List.of(newFile));
		}

		return true;
	}

}
