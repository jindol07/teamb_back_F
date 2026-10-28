package kr.co.alpharking.repository.mypage;

import java.util.List;
import java.util.Optional;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.dto.mypage.MyPageDtos.ChargeRow;
import kr.co.alpharking.entity.mypage.OfficeCharge;

public interface OfficeChargeRepository extends JpaRepository<OfficeCharge, Long> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from OfficeCharge c where c.officeId = :officeId and c.yearMonth = :yearMonth order by c.id desc")
    // 패널티를 추가할 당월 청구들을 잠그고 최신 청구부터 조회한다.
    List<OfficeCharge> lockCurrent(@Param("officeId") Long officeId, @Param("yearMonth") String yearMonth);

    @Query("""
        select c.id as id, c.yearMonth as yearMonth, c.totalAmount as totalAmount,
               c.mileageDiscountAmount as mileageDiscountAmount, c.finalAmount as finalAmount,
               c.statusCode as statusCode, d.codeName as statusName
        from OfficeCharge c
        left join MyPageCommonCodeDetail d on d.id.groupCode = 'CHARGE_STATUS' and d.id.code = c.statusCode
        where c.officeId = :officeId and c.yearMonth = :yearMonth
        order by c.id desc
        """)
    // 본인 사무실의 당월 관리비와 공통코드 상태명을 함께 조회한다.
    List<ChargeRow> findCurrent(@Param("officeId") Long officeId, @Param("yearMonth") String yearMonth);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from OfficeCharge c where c.id = :id and c.officeId = :officeId")
    // 본인 소유의 청구 행에 쓰기 잠금을 걸고 갱신 대상으로 조회한다.
    Optional<OfficeCharge> lockOwned(@Param("id") Long id, @Param("officeId") Long officeId);
}
