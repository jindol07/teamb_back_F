/** 파일 안내
 * 용도: U HTTP·소켓용 읽기 전용 구획 조회 서비스.
 * 사용처·연결: U ParkingSpaceController와 ParkingSpacePollingTask → ParkingSpaceQueryRepository.
 * 읽기 전용 트랜잭션 경계를 제공한다. A의 관리자 보정·쓰기 기능과 통합하지 않는다.
 */
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

    // HTTP와 소켓 공통 조회의 읽기 전용 트랜잭션 경계다. 쓰기나 관리자 보정은 수행하지 않는다.
    @Transactional(readOnly = true)
    public List<ParkingSpacePublicRow> findAll() {
        return repository.findAll();
    }
}
