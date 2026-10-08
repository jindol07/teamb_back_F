package kr.co.alpharking.dto.notice;

import java.util.Date;
import java.util.List;
import java.util.stream.Collectors;

import org.springframework.web.multipart.MultipartFile;

import kr.co.alpharking.entity.notice.Notice;
import lombok.Builder;
import lombok.Data;
import lombok.Getter;
import lombok.Setter;

@Data
@Getter
@Builder
public class NoticeRes {
	private Integer num;
	//private Integer writerAdminId;
	private Integer writerAdminNm;
	//private String noticeTypeCode;
	private String noticeTypeNm;
	private String title;
	private String content;
	private int viewCount;
	private Date ndate;
	//1:N 즉 collection관계 
    //private List<NoticeFiles> getfilelist;
	private List<MultipartFile> files;
	private List<NoticeAttachmentRes> fileList;
	
	//Entity -> DTO 변환을 위한 정적 팩토리 메서드 추가
    public static NoticeRes from(Notice notice) {
        return NoticeRes.builder()
                .num(notice.getNoticeId())
                .title(notice.getTitle())
                .content(notice.getContent())
                .viewCount(notice.getViewCount())
                // 자식 Entity -> 자식 DTO 변환
                .fileList(notice.getFileList().stream()
                        .map(NoticeAttachmentRes::from)
                        .collect(Collectors.toList()))
                .build();
    }
}
