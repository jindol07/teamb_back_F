package kr.co.alpharking.dto.notice;

import org.apache.ibatis.type.Alias;

import lombok.Getter;
import lombok.Setter;

@Alias("nfdto")
@Getter
@Setter
public class NoticeFiles {
	private int noticeAttachmentId;
	private int noticeId;
	private String originalName;
	private String storedName;
	private String filePath;
	private int fileSize;
	private String createdAt;
}
