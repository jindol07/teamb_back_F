package kr.co.alpharking.repository.mypage;

import java.util.Optional;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.security.Office;

public interface MyPageOfficeRepository extends JpaRepository<Office, Long> {
    // by팀장: 관리자 마일리지 차감과 동일한 OFFICE 행을 가장 먼저 잠근다.
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select o from Office o where o.office_id = :officeId")
    Optional<Office> lockOffice(@Param("officeId") Long officeId);

    @Modifying(flushAutomatically = true)
    @Query(value = "UPDATE OFFICE SET UPDATED_AT = SYSDATE WHERE OFFICE_ID = :officeId", nativeQuery = true)
    // 지정한 사무실의 수정일을 DB의 현재 시각으로 갱신한다.
    int updateTimestamp(@Param("officeId") Long officeId);

    @Query("""
        select count(o) from Office o where o.company_id = :companyId and o.office_id <> :officeId
        and (o.withdrawn_at is null or o.status_code <> 'WITHDRAWN')
        """)
    // 같은 회사에 남아 있는 다른 미탈퇴 회원 수를 조회한다.
    long countOtherMembers(@Param("companyId") Long companyId, @Param("officeId") Long officeId);

    @Query("""
        select count(o) from Office o where o.office_id <> :officeId and
        (o.username = :username or o.email = :email or (:phone is not null and o.phone = :phone))
        """)
    // 탈퇴용 로그인 ID·이메일·전화번호가 다른 사무실과 충돌하는지 검사한다.
    long countUniqueConflicts(@Param("officeId") Long officeId, @Param("username") String username,
            @Param("email") String email, @Param("phone") String phone);

    @Query(value = "SELECT TO_CHAR(SYSDATE, 'MMDD') FROM dual", nativeQuery = true)
    // 탈퇴 접미사에 사용할 DB 기준 월일을 MMdd 형식으로 조회한다.
    String deletionDay();

    @Modifying(flushAutomatically = true, clearAutomatically = true)
    @Query(value = """
        UPDATE OFFICE SET LOGIN_ID = :username, EMAIL = :email, PHONE = :phone,
            STATUS_CODE = 'WITHDRAWN', WITHDRAWN_AT = SYSDATE, UPDATED_AT = SYSDATE,
            PASSWORD_HASH = :disabledPassword
        WHERE OFFICE_ID = :officeId AND STATUS_CODE = 'ACTIVE' AND WITHDRAWN_AT IS NULL
        """, nativeQuery = true)
    // 사무실의 유니크 값·탈퇴일·상태·비밀번호 해시를 갱신해 소프트 삭제한다.
    int withdraw(@Param("officeId") Long officeId, @Param("username") String username,
            @Param("email") String email, @Param("phone") String phone,
            @Param("disabledPassword") String disabledPassword);
}
