
package kr.co.alpharking.dao.notice;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.dto.notice.NoticeFiles;
import kr.co.alpharking.dto.notice.NoticeHistory;

@Mapper
public interface NoticeDao {

	// 공지사항 등록
	void add(NoticeCreateReq nidto);

	// 첨부파일 등록
	void addfile(List<NoticeFiles> nfvo);

	// 첨부파일 고유번호 생성
	Integer nextAttachmentId();

	// 공지사항 목록 조회
	List<NoticeCreateReq> findAll();

	// 공지사항 상세 조회
	NoticeCreateReq findById(Integer noticeId);

	// 특정 공지사항의 첨부파일 조회
	List<NoticeFiles> findFilesByNoticeId(Integer noticeId);

	// 기존 첨부파일 정보를 새 파일 정보로 수정
	int updateNoticeFile(NoticeFiles nfdto);

	// DB 현재 시각 조회
	String getCurrentDateTime();

	// 공지사항 수정
	int updateNotice(@Param("nidto") NoticeCreateReq nidto, @Param("changedAt") String changedAt);

	// 공지사항 소프트 삭제
	int deleteNotice(@Param("noticeId") Integer noticeId, @Param("changedAt") String changedAt);

	// 공지사항 변경 이력 저장
	int insertNoticeHistory(NoticeHistory nhdto);

	// 특정 공지사항의 변경 이력 목록 조회
	List<NoticeHistory> findNoticeHistoryByNoticeId(Integer noticeId);
	
	// 현재 유효한 공지사항 버전의 종료 시각 설정
	int closeCurrentNoticeHistory(
	    @Param("noticeId") Integer noticeId,
	    @Param("changedAt") String changedAt
	);
}
