package kr.co.alpharking.repository.mypage;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.dto.mypage.MyPageDtos.AcceptedReportRow;
import kr.co.alpharking.entity.report.ReportEntity;

public interface MyPageReportRepository extends JpaRepository<ReportEntity, Long> {
    // 신고자 officeId가 아니라 대상 차량의 소유자를 검사한다. 신고자 정보·신고 원문은 반환하지 않는다.
    @Query(value = """
        select r.reportId as id, r.targetVehicleNumber as vehicleNumber, t.codeName as typeName,
               s.codeName as statusName, r.reviewReason as reviewReason,
               r.createdAt as createdAt, r.reviewedAt as reviewedAt
        from ReportEntity r
        join Vehicle v on v.vehicleId = r.targetVehicleId
        left join MyPageCommonCodeDetail t on t.id.groupCode = 'REPORT_TYPE' and t.id.code = r.reportTypeCode
        left join MyPageCommonCodeDetail s on s.id.groupCode = 'REPORT_STATUS' and s.id.code = r.statusCode
        where v.officeId = :officeId and r.statusCode = 'ACCEPTED'
        order by r.reviewedAt desc, r.reportId desc
        """, countQuery = """
        select count(r) from ReportEntity r join Vehicle v on v.vehicleId = r.targetVehicleId
        where v.officeId = :officeId and r.statusCode = 'ACCEPTED'
        """)
    // 대상 차량의 소유 사무실을 기준으로 승인 신고와 공통코드 표시명을 페이징 조회한다.
    Page<AcceptedReportRow> findOwned(@Param("officeId") Long officeId, Pageable pageable);
}
