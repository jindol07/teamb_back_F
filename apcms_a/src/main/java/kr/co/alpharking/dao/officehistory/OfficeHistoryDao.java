/**
 * 용도: office-history.xml의 사무실 이력 조회와 서비스를 연결하는 MyBatis 매퍼.
 * 사용처: OfficeHistoryService.findAll. 쓰기 메서드는 제공하지 않는다.
 */
package kr.co.alpharking.dao.officehistory;

import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import kr.co.alpharking.dto.officehistory.OfficeHistoryRow;

@Mapper
public interface OfficeHistoryDao {
    List<OfficeHistoryRow> findAll();
}
