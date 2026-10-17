
package kr.co.alpharking.repository.notice;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import kr.co.alpharking.entity.notice.Notice;

public interface NoticeRepository extends JpaRepository<Notice, Integer> {

	// 사용자 공지사항 목록 조회 + 제목 검색 + 유형 필터
	@EntityGraph(attributePaths = { "fileList" })
	@Query("""
			SELECT n
			FROM Notice n
			WHERE n.deletedAt IS NULL
			  AND (
			      :keyword IS NULL
			      OR LOWER(n.title) LIKE LOWER(
			          CONCAT('%', :keyword, '%')
			      )
			  )
			  AND (
			      :type IS NULL
			      OR n.noticeTypeCode = :type
			  )
			ORDER BY
			    n.pinnedYn DESC,
			    n.createdAt DESC,
			    n.noticeId DESC
			""")
	List<Notice> searchNotices(@Param("keyword") String keyword, @Param("type") String type);

	// noticeId 공지사항 조회
	// DeletedAt null공지사항 조회
	// fileList 연결된 첨부파일도 조회
	@EntityGraph(attributePaths = { "fileList" })
	Optional<Notice> findByNoticeIdAndDeletedAtIsNull(Integer noticeId);

	@Modifying
	@Query("""
			UPDATE Notice n
			SET n.viewCount = n.viewCount + 1
			WHERE n.noticeId = :noticeId
			  AND n.deletedAt IS NULL
			""")
	int increaseViewCount(@Param("noticeId") Integer noticeId);

}
