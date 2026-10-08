package kr.co.alpharking.dto.notice;

import kr.co.alpharking.entity.notice.NoticeAttachment;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class NoticeAttachmentRes {
	private Integer noticeAttachmentId;
    private String originalName;
    private String filePath;
    
    public static NoticeAttachmentRes from(NoticeAttachment attachment) {
        return NoticeAttachmentRes.builder()
                .noticeAttachmentId(attachment.getNoticeAttachmentId())
                .originalName(attachment.getOriginalName())
                .filePath(attachment.getFilePath())
                .build();
    }

}
