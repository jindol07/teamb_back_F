package kr.co.alpharking.service.parking;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import kr.co.alpharking.dao.parking.ParkingSpaceDao;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;

@Service
public class ParkingSpaceService {
    private final ParkingSpaceDao dao;
    public ParkingSpaceService(ParkingSpaceDao dao) { this.dao = dao; }

    @Transactional(readOnly = true)
    public List<ParkingSpaceRow> findAllAdmin() { return dao.findAllAdmin(); }

    @Transactional(readOnly = true)
    public List<ParkingSpacePublicRow> findAllPublic() { return dao.findAllPublic(); }
}
