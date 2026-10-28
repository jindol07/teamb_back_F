package kr.co.alpharking.repository.mypage;

import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.dto.mypage.MyPageDtos.ChargeItemRow;
import kr.co.alpharking.entity.mypage.OfficeChargeItem;

public interface OfficeChargeItemRepository extends JpaRepository<OfficeChargeItem, Long> {
    // 패널티 행 잠금이 확보된 뒤 해당 금액이 이미 청구됐는지 최신 상태로 다시 검사한다.
    boolean existsByChargeTypeCodeAndReferenceId(String chargeTypeCode, Long referenceId);

    @Query("""
        select i.id as id, i.chargeId as chargeId, d.codeName as typeName,
               i.amount as amount, i.description as description
        from OfficeChargeItem i
        join OfficeCharge c on c.id = i.chargeId
        left join MyPageCommonCodeDetail d on d.id.groupCode = 'CHARGE_TYPE' and d.id.code = i.chargeTypeCode
        where c.officeId = :officeId and c.yearMonth = :yearMonth
        order by i.id asc
        """)
    // 본인 사무실의 당월 청구 항목과 공통코드 유형명을 일괄 조회한다.
    List<ChargeItemRow> findCurrent(@Param("officeId") Long officeId, @Param("yearMonth") String yearMonth);
}
