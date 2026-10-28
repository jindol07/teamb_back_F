package kr.co.alpharking.repository.mypage;

import java.time.LocalDateTime;
import java.util.List;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.dto.mypage.MyPageDtos.PenaltyRow;
import kr.co.alpharking.entity.mypage.VehiclePenalty;

public interface MyPagePenaltyRepository extends JpaRepository<VehiclePenalty, Long> {
    @Query(value = """
        select p.id as id, v.vehicleNumber as vehicleNumber, d.codeName as typeName,
               p.amount as penaltyAmount, p.reason as reason, p.imposedAt as imposedAt
        from MyPageVehiclePenalty p
        join Vehicle v on v.vehicleId = p.vehicleId
        join Office o on o.office_id = v.officeId
        left join MyPageCommonCodeDetail d on d.id.groupCode = 'VIOLATION_TYPE' and d.id.code = p.violationTypeCode
        where o.office_id = :officeId
        order by p.imposedAt desc, p.id desc
        """, countQuery = """
        select count(p) from MyPageVehiclePenalty p join Vehicle v on v.vehicleId = p.vehicleId
        join Office o on o.office_id = v.officeId where o.office_id = :officeId
        """)
    // 본인 사무실 소속 차량에 실제 부과된 패널티와 위반 금액을 페이지로 조회한다.
    Page<PenaltyRow> findOwned(@Param("officeId") Long officeId, Pageable pageable);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("""
        select p from MyPageVehiclePenalty p join Vehicle v on v.vehicleId = p.vehicleId
        where v.officeId = :officeId and p.imposedAt >= :start and p.imposedAt < :end and p.amount > 0
        and not exists (select i.id from OfficeChargeItem i where i.chargeTypeCode = 'PENALTY' and i.referenceId = p.id)
        order by p.id asc
        """)
    // 당월에 부과됐고 어느 청구에도 반영되지 않은 양수 패널티를 잠가 조회한다.
    List<VehiclePenalty> lockUnbilled(@Param("officeId") Long officeId,
            @Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
}
