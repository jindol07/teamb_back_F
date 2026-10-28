package kr.co.alpharking.repository.mypage;

import java.util.Optional;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.security.Company;

public interface MyPageCompanyRepository extends JpaRepository<Company, Long> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from Company c where c.company_id = :companyId")
    // 탈퇴 대상 회사 행에 비관적 쓰기 잠금을 걸어 동시에 변경되지 않게 한다.
    Optional<Company> lockCompany(@Param("companyId") Long companyId);

    @Query("select count(c) from Company c where c.company_id <> :companyId and c.business_number = :number")
    // 변경할 사업자번호가 다른 회사의 유니크 값과 충돌하는지 조회한다.
    long countBusinessConflicts(@Param("companyId") Long companyId, @Param("number") String number);

    @Modifying(flushAutomatically = true, clearAutomatically = true)
    @Query(value = """
        UPDATE COMPANY SET BUSINESS_NUMBER = :number, DELETED_AT = SYSDATE, UPDATED_AT = SYSDATE
        WHERE COMPANY_ID = :companyId AND DELETED_AT IS NULL
        """, nativeQuery = true)
    // 회사의 사업자번호를 변경하고 삭제일과 수정일을 DB 현재 시각으로 기록한다.
    int softDelete(@Param("companyId") Long companyId, @Param("number") String number);
}
