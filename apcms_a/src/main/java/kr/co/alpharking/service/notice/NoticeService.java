
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

    // 공지사항 등록 및 첨부파일 등록
    @Transactional
    public void transcationProcess(NoticeCreateReq nidto, List<NoticeFiles> nfvo) {

        // 1. 공지사항 등록
        noticeDao.add(nidto);

        // 2. 첨부파일이 있을 경우에만 실행
        if (nfvo != null && !nfvo.isEmpty()) {

            // 3. 등록된 공지사항 번호 가져오기
            Integer noticeId = nidto.getNoticeId();

            // 4. 각 첨부파일에 번호 설정
            for (NoticeFiles file : nfvo) {

                // 공지사항 번호 설정
                file.setNoticeId(noticeId);

                // 첨부파일 고유번호 생성
                file.setNoticeAttachmentId(noticeDao.nextAttachmentId());
            }

            // 5. 첨부파일 목록 DB 등록
            noticeDao.addfile(nfvo);
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

    // 공지사항 수정 및 수정 전 이력 저장
    @Transactional
    public boolean updateNotice(NoticeCreateReq nidto, Long changedByAdminId) {

        // 1. 수정 전 공지사항 조회
        NoticeCreateReq oldNotice = noticeDao.findById(nidto.getNoticeId());

        // 2. 공지사항이 없으면 false 반환
        if (oldNotice == null) {
            return false;
        }

        // 3. 변경 관리자 번호 확인
        if (changedByAdminId == null) {
            throw new IllegalArgumentException("변경 관리자 번호가 필요합니다.");
        }

        // 4. DB 현재 시각 조회
        String changedAt = noticeDao.getCurrentDateTime();

        // 5. 수정 전 데이터로 이력 객체 생성
        NoticeHistory history = createNoticeHistory(
                oldNotice,
                changedByAdminId,
                "UPDATE",
                "공지사항 수정",
                changedAt
        );

        // 6. NOTICE_HISTORY에 수정 전 데이터 저장
        noticeDao.insertNoticeHistory(history);

        // 7. NOTICE 테이블의 공지사항 수정
        int result = noticeDao.updateNotice(nidto, changedAt);

        // 8. 수정 실패 시 이력 저장도 롤백
        if (result == 0) {
            throw new IllegalStateException("공지사항 수정에 실패했습니다.");
        }

        return true;
    }

    // 공지사항 소프트 삭제 및 삭제 전 이력 저장
    @Transactional
    public boolean deleteNotice(Integer noticeId, Long changedByAdminId) {

        // 1. 삭제 전 공지사항 조회
        NoticeCreateReq oldNotice = noticeDao.findById(noticeId);

        // 2. 공지사항이 없으면 false 반환
        if (oldNotice == null) {
            return false;
        }

        // 3. 변경 관리자 번호 확인
        if (changedByAdminId == null) {
            throw new IllegalArgumentException("변경 관리자 번호가 필요합니다.");
        }

        // 4. DB 현재 시각 조회
        String changedAt = noticeDao.getCurrentDateTime();

        // 5. 삭제 전 데이터로 이력 객체 생성
        NoticeHistory history = createNoticeHistory(
                oldNotice,
                changedByAdminId,
                "DELETE",
                "공지사항 삭제",
                changedAt
        );

        // 6. NOTICE_HISTORY에 삭제 전 데이터 저장
        noticeDao.insertNoticeHistory(history);

        // 7. NOTICE 테이블의 삭제 시간 기록
        int result = noticeDao.deleteNotice(noticeId, changedAt);

        // 8. 삭제 실패 시 이력 저장도 롤백
        if (result == 0) {
            throw new IllegalStateException("공지사항 삭제에 실패했습니다.");
        }

        return true;
    }

    // 특정 공지사항의 변경 이력 목록 조회
    public List<NoticeHistory> getNoticeHistoryList(Integer noticeId) {

        return noticeDao.findNoticeHistoryByNoticeId(noticeId);
    }

    // 수정 및 삭제 전 공지사항 데이터를 이력 객체로 변환
    private NoticeHistory createNoticeHistory(
            NoticeCreateReq notice,
            Long changedByAdminId,
            String changeTypeCode,
            String changeReason,
            String changedAt) {

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
        history.setValidFrom(
                notice.getUpdatedAt() != null
                        ? notice.getUpdatedAt()
                        : notice.getCreatedAt()
        );

        // 7. 기존 버전의 유효 종료 시각
        history.setValidTo(changedAt);

        return history;
    }
}
