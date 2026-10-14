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
}
