package kr.co.alpharking.dao.mileage;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import kr.co.alpharking.dto.mileage.MileagehistoryDto;

@Repository
public interface MileagehistoryDao extends JpaRepository<MileagehistoryDto, Long> {
    @Query("select m from MileagehistoryDto m where m.office.office_id = :officeId order by m.createdat desc")
    java.util.List<MileagehistoryDto> findAllByOfficeIdOrderByCreatedatDesc(@Param("officeId") Long officeId);
}
