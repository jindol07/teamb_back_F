package kr.co.alpharking.dto.notice;

import java.util.List;

import org.apache.ibatis.type.Alias;

import lombok.Getter;
import lombok.Setter;

@Alias("nidto")
@Getter
@Setter
public class NoticeCreateReq {
	private Integer noticeId;
	private Integer writerAdminId;
	private String noticeTypeCode;
	private String title;
	private String content;
	private int viewCount;
	// 목록의 첨부 아이콘 표시용: 파일별 상세 조회 없이 개수만 전달합니다.
	private int attachmentCount;
	private String createdAt;
	private String updatedAt;
	private String deletedAt;
	//1:N 즉 collection관계 
    private List<NoticeFiles> getfilelist;
    //10/13
    private String importantYn = "N"; // 중요 공지 여부
    private String pinnedYn = "N";    // 상단 고정 여부
	
}
