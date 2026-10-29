/**
 * 용도: 사무실 계정 이력의 읽기 전용 조회.
 * 사용처: OfficeHistoryController → OfficeHistoryDao → office-history.xml.
 */
package kr.co.alpharking.service.officehistory;

import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import kr.co.alpharking.dao.officehistory.OfficeHistoryDao;
import kr.co.alpharking.dto.officehistory.OfficeHistoryRow;

@Service
public class OfficeHistoryService {
    private final OfficeHistoryDao dao;

    public OfficeHistoryService(OfficeHistoryDao dao) {
        this.dao = dao;
    }

    @Transactional(readOnly = true)
    public List<OfficeHistoryRow> findAll() {
        return dao.findAll();
    }
}
