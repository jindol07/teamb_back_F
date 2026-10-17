
package kr.co.alpharking.dto.notice;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

import kr.co.alpharking.entity.notice.Notice;
import lombok.Builder;
import lombok.Data;

// @Data @getter 기능이 포함되어잇음
@Data
@Builder
public class NoticeRes {

    private Integer num;
    private Integer writerAdminId;
    private String noticeTypeCode;

    private String title;
    private String content;
    private int viewCount;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    private String importantYn;
    private String pinnedYn;

    private List<NoticeAttachmentRes> fileList;

    // Entity → DTO 변환
    public static NoticeRes from(Notice notice) {
        return NoticeRes.builder()
                .num(notice.getNoticeId())
                .writerAdminId(notice.getWriterAdminId())
                .noticeTypeCode(notice.getNoticeTypeCode())
                .title(notice.getTitle())
                .content(notice.getContent())
                .viewCount(notice.getViewCount())
                .createdAt(notice.getCreatedAt())
                .updatedAt(notice.getUpdatedAt())
                .importantYn(notice.getImportantYn())
                .pinnedYn(notice.getPinnedYn())
                .fileList(notice.getFileList().stream()
                        .map(NoticeAttachmentRes::from)
                        .collect(Collectors.toList()))
                .build();
    }
}
