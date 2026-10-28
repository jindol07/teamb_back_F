package kr.co.alpharking.repository.mypage;

import java.math.BigDecimal;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import kr.co.alpharking.dto.mileage.MileagehistoryDto;

public interface MyPageMileageRepository extends JpaRepository<MileagehistoryDto, Long> {
    // by팀장: 기존 화면과 동일하게 과거 양수 USE도 음수로 합산한다. 집계 자체에는 행 잠금을 걸지 않는다.
    @Query(value = """
        SELECT NVL(SUM(CASE WHEN MILEAGE_TYPE_CODE = 'USE' THEN -ABS(AMOUNT) ELSE AMOUNT END), 0)
        FROM MILEAGE_HISTORY WHERE OFFICE_ID = :officeId
        """, nativeQuery = true)
    BigDecimal balance(@Param("officeId") Long officeId);
}
