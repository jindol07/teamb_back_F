package kr.co.alpharking.security;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface UserRepository extends JpaRepository<Office, Long>{
	 // jdk8 이후 사용
    // 결과가 없는 경우 Optional.empty()를 반환, 결과가 있는 경우 Optional.of(결과)를 반환
    // 데이터베이스에서 사용자를 가져오거나 사용자를 반환,아니면 Optional.empty()를 반환
	Optional<Office> findByUsername(String username);
	
	boolean existsByUsername(String username);
	
	@Query("""
	    SELECT CASE WHEN COUNT(o) > 0 THEN true ELSE false END
	    FROM Office o
	    WHERE o.company_id = :companyId
	      AND o.floor_no = :floorNo
	      AND o.office_number = :officeNumber
	""")
	boolean existsDuplicateOffice(
	    @Param("companyId") Long companyId,
	    @Param("floorNo") Long floorNo,
	    @Param("officeNumber") String officeNumber
	);

	// ------------------------------------------------------------------
	// 네이버 로그인 연동용 (기존 카카오 방식과 동일하게 컬럼으로 관리)
	// 엔티티 필드명이 naver_user_id 이므로 JPQL로 조회한다.
	// ------------------------------------------------------------------
	@Query("select o from Office o where o.naver_user_id = :naverUserId")
	Optional<Office> findByNaverUserId(@Param("naverUserId") String naverUserId);

	List<Office> findByEmailIgnoreCase(String email);
}
