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
	private String createdAt;
	private String updatedAt;
	private String deletedAt;
	//1:N 즉 collection관계 
    private List<NoticeFiles> getfilelist;
	
}
