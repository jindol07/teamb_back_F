/** 파일 안내
 * 용도: AI 점유 이벤트·구획 상태·이력 SQL의 MyBatis 인터페이스.
 * 사용처·연결: AiOccupancyService → mapper/ai-parking-occupancy.xml.
 * insertEvent의 Map에는 selectKey가 생성한 aiDetectionEventId가 채워져 서비스로 돌아온다.
 */
package kr.co.alpharking.dao.parking;

import java.time.LocalDateTime;
import java.util.Map;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;

@Mapper
public interface AiOccupancyDao {
    // 점유 이벤트의 대상 구획을 AI 코드로 찾고 행 잠금한다.
    ParkingSpaceRow lockByCode(@Param("spaceCode") String spaceCode);
    // 해당 구획에서 기존 JSON event_id 검색 결과 수 조회.
    int countEventId(@Param("parkingSpaceId") Long id, @Param("needle") String needle);
    // PARKING_OCCUPANCY 유형의 최신 감지 시각 조회.
    LocalDateTime latestOccupancyDetectedAt(@Param("parkingSpaceId") Long id);
    // 감지 이벤트 저장 및 Map의 aiDetectionEventId에 생성된 PK 반환.
    int insertEvent(Map<String, Object> params);
    // 구획 상태·수정 시각 갱신 건수 반환.
    int updateStatus(@Param("parkingSpaceId") Long id, @Param("status") String status);
    // 해당 구획의 열린 상태 이력을 종료한다.
    int closeHistory(@Param("parkingSpaceId") Long id);
    // 현재 구획 스냅샷을 AI 출처·감지 이벤트 ID와 함께 저장한다.
    int insertHistory(@Param("parkingSpaceId") Long id,
                      @Param("aiDetectionEventId") Long eventId);
}
