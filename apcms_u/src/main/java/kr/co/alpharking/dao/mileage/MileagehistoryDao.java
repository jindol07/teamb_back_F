package kr.co.alpharking.dao.mileage;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import kr.co.alpharking.dto.mileage.MileagehistoryDto;

@Repository
public interface MileagehistoryDao extends JpaRepository<MileagehistoryDto, Long> {
}