package kr.co.alpharking.dao.mileage;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import kr.co.alpharking.dto.mileage.MileagehistoryDto;

/* JPA 저장소 for mileage history records. */
@Repository
public interface MileagehistoryDao extends JpaRepository<MileagehistoryDto, Long> {
}