package kr.co.alpharking.dto.notice;

import org.apache.ibatis.type.Alias;
import lombok.Getter;
import lombok.Setter;

@Alias("nhdto")
@Getter
@Setter
public class NoticeHistory {
	// 이력 고유번호
	private Long noticeHistoryId;
	// 원본 공지사항 번호
	private Long noticeId;
	// 최초 작성 관리자 번호
	private Long writerAdminId;
	// 공지사항 유형
	private String noticeTypeCode;
	// 공지사항 제목
	private String title;
	// 공지사항 내용
	private String content;
	// 조회수
	private int viewCount;
	// 공지사항 등록일
	private String createdAt;
	// 공지사항 수정일
	private String updatedAt;
	// 공지사항 삭제일
	private String deletedAt;
	// 변경을 수행한 관리자 번호
	private Long changedByAdminId;
	// 변경 주체 유형
	private String actorTypeCode;
	// 변경 주체 번호
	private Long actorId;
	// 변경 유형
	private String changeTypeCode;
	// 변경 사유
	private String changeReason;
	// 해당 버전의 시작 시점
	private String validFrom;
	// 해당 버전의 종료 시점
	private String validTo;
	// 중요 공지 여부
	private String importantYn;
	// 상단 고정 여부
	private String pinnedYn;

	// 첨부파일 변경 전 정보
	//int 대신 Integer인 이유는 첨부파일이 없는 경우 null일 수 있기 때문
	private Integer noticeAttachmentId; // 첨부파일 고유번호 
	private String originalName; // 원본 파일명
	private String storedName; // 서버 저장 파일명
	private String filePath; // 실제 파일 저장 경로
	private int fileSize; // 파일 크기

}
