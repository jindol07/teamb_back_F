package kr.co.alpharking.repository.notice;

import java.util.List;

import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import kr.co.alpharking.entity.notice.Notice;

public interface NoticeRepository extends JpaRepository<Notice, Integer>{
	
	// 최신순으로 정렬된 Notice 목록을 반환하는 메서드
	@EntityGraph(attributePaths = {"fileList"}) //자식 테이블
    List<Notice> findAllByOrderByNoticeIdDesc();
	
}
