package kr.co.alpharking.security;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface CompanyRepository extends JpaRepository<Company, Long> {

    @Query("""
        SELECT CASE WHEN COUNT(c) > 0 THEN true ELSE false END
        FROM Company c
        WHERE c.business_number = :businessNumber
    """)
    boolean existsDuplicateBusinessNumber(
        @Param("businessNumber") String businessNumber
    );
}
