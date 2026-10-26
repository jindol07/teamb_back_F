package kr.co.alpharking.repository.report;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import kr.co.alpharking.entity.report.ReportEntity;

@Repository
public interface ReportRepository extends JpaRepository<ReportEntity, Long> {
}
