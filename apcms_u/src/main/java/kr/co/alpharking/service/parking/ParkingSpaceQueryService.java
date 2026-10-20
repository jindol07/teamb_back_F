package kr.co.alpharking.service.parking;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;
import kr.co.alpharking.repository.parking.ParkingSpaceQueryRepository;

@Service
public class ParkingSpaceQueryService {
    private final ParkingSpaceQueryRepository repository;

    public ParkingSpaceQueryService(ParkingSpaceQueryRepository repository) {
        this.repository = repository;
    }

    @Transactional(readOnly = true)
    public List<ParkingSpacePublicRow> findAll() {
        return repository.findAll();
    }
}
