/** [1023_1010] 파일 안내
 * 용도: 입출차·구획 연결·기존 미출차 기록 SQL의 MyBatis 인터페이스.
 * 사용처·연결: ParkingUsageService, AiVehicleEventService, ParkingSpaceService → mapper/parking-usage.xml.
 * 행 잠금·갱신 결과 건수는 서비스 트랜잭션의 정합성 판단에 사용된다.
 */
package kr.co.alpharking.dao.parking;

import java.util.List;
import java.sql.Timestamp;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import kr.co.alpharking.dto.parking.ParkingUsageRow;

@Mapper
public interface ParkingUsageDao {
    // [1023_1010] 승인 등록 차량을 잠그고 PK를 읽는다. 해당 차량이 없으면 null이다.
    Long lockRegisteredVehicle(@Param("number") String number);
    // [1023_1010] 번호판에 대한 미출차 이용 기록 ID 조회.
    Long findOpenUsageByPlate(@Param("number") String number);
    // [1023_1010] 등록·방문 유형과 감지 시각으로 입차 INSERT. 변경 건수를 반환한다.
    int insertEntry(@Param("vehicleId") Long vehicleId, @Param("number") String number, @Param("parkingType") String parkingType, @Param("eventTime") Timestamp eventTime);
    // [1023_1010] 같은 DB 세션의 시퀀스 CURRVAL로 방금 생성한 이용 기록 PK를 읽는다.
    Long insertedUsageId();
    // [1023_1010] 지연 입차 이벤트 검사용 최근 출차 시각 조회.
    java.sql.Timestamp findLatestExitByPlate(@Param("number") String number);
    // [1023_1010] 층·구역·번호로 구성된 AI 구획 코드를 DB PK로 변환한다.
    Long findSpaceIdByCode(@Param("spaceCode") String spaceCode);
    // [1023_1010] PK로 단건 결과를 조회한다. 반환 DTO와 실제 조인은 연결 XML에서 정의한다.
    ParkingUsageRow findById(@Param("id") Long id);
    // [1023_1010] 미출차 상태인 이용 기록만 잠그고 반환한다.
    ParkingUsageRow lockOpenUsage(@Param("id") Long id);
    // [1023_1010] 전체 미출차 이용 기록 조회. 최근 목록 제한과 무관하다.
    List<ParkingUsageRow> findActive();
    // [1023_1010] 최근 입출차 목록 최대 200건 조회.
    List<ParkingUsageRow> findRecent();
    // [1023_1010] 배정 대상 구획 상태를 행 잠금으로 읽는다.
    String lockSpaceStatus(@Param("spaceId") Long spaceId);
    // [1023_1010] 해당 이용 기록 외에 같은 구획에 연결된 미출차 기록 수 조회.
    int countOtherActiveOnSpace(@Param("spaceId") Long spaceId, @Param("usageId") Long usageId);
    // [1023_1010] 미출차 이용 기록에 구획을 연결한 갱신 건수 반환.
    int assignSpace(@Param("usageId") Long usageId, @Param("spaceId") Long spaceId);
    // [1023_1010] 미출차 이용 기록의 출차 시각 갱신 건수 반환.
    int exitUsage(@Param("usageId") Long usageId, @Param("eventTime") Timestamp eventTime);
    // [1023_1010] 보정 상세에 표시할 해당 구획의 미출차 기록 조회.
    List<ParkingUsageRow> findActiveOnSpace(@Param("spaceId") Long spaceId);
    // [1023_1010] 보정 시 해당 구획의 미출차 기록을 ID 순으로 NOWAIT 잠금 조회.
    List<ParkingUsageRow> lockActiveOnSpace(@Param("spaceId") Long spaceId);
    // [1023_1010] 번호판 부분 일치 미출차 기록 최대 30건 조회.
    List<ParkingUsageRow> searchActive(@Param("number") String number);
    // [1023_1010] 같은 번호판의 활성 기록 수를 확인하여 모호한 보정 연결을 차단한다.
    int countActiveByPlate(@Param("number") String number);
    // [1023_1010] 지정 구획과의 연결만 해제하고 입차·출차 기록은 유지한다.
    int detachSpace(@Param("usageId") Long usageId, @Param("spaceId") Long spaceId);
}
