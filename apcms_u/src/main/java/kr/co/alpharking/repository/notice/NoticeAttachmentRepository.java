
package kr.co.alpharking.repository.notice;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import kr.co.alpharking.entity.notice.NoticeAttachment;

public interface NoticeAttachmentRepository
        extends JpaRepository<NoticeAttachment, Integer> {

    // 특정 공지사항에 속한 첨부파일 조회
    Optional<NoticeAttachment> findByNoticeAttachmentIdAndNotice_NoticeId(
            Integer noticeAttachmentId,
            Integer noticeId);
}
