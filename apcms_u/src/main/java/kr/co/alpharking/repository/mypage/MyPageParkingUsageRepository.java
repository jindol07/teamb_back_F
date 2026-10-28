package kr.co.alpharking.repository.mypage;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.dto.mypage.MyPageDtos.ParkingUsageRow;
import kr.co.alpharking.recmnTest.PrkUsage;

public interface MyPageParkingUsageRepository extends JpaRepository<PrkUsage, Long> {
    @Query(value = """
        select u.parkingUsageId as id, u.vehicleNumber as vehicleNumber, u.entryAt as entryAt,
               u.exitAt as exitAt, d.codeName as parkingTypeName
        from PrkUsage u
        left join MyPageCommonCodeDetail d on d.id.groupCode = 'PARKING_TYPE' and d.id.code = u.parkingTypeCode
        where u.officeId = :officeId
        order by u.entryAt desc, u.parkingUsageId desc
        """, countQuery = "select count(u) from PrkUsage u where u.officeId = :officeId")
    // 본인 사무실의 주차 이용 이력과 유형명을 최신 입차순으로 페이징 조회한다.
    Page<ParkingUsageRow> findOwned(@Param("officeId") Long officeId, Pageable pageable);
}
