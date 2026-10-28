/** 파일 안내
 * 용도: 구획·예약·관리자 보정 이력 SQL의 MyBatis 인터페이스.
 * 사용처·연결: ParkingSpaceService, AiOccupancyService, A ParkingWebSocketHandler → mapper/parking-space.xml.
 * 각 메서드명은 XML statement id, @Param 이름은 SQL 바인딩 이름과 연결된다.
 */
package kr.co.alpharking.dao.parking;

import java.util.List;
import kr.co.alpharking.dto.parking.ParkingReservationRow;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Mapper;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;
import kr.co.alpharking.dto.parking.ParkingSpaceHistoryRow;
import java.sql.Timestamp;

@Mapper
public interface ParkingSpaceDao {
    // 전체 날짜 예약 이력: 과거·취소 포함. XML findReservationHistory와 연결된다.
    List<ParkingReservationRow> findReservationHistory(@Param("spaceId") Long spaceId);
    // 조건에 맞는 확정 예약 조회. startAt/endAt/spaceId는 XML의 바인딩 이름이다.
    List<ParkingReservationRow> findReservations(
            @Param("spaceId") Long spaceId, @Param("startAt") Timestamp startAt,
            @Param("endAt") Timestamp endAt);
    // 관리자 원본 현황·메모·조건부 차량번호 조회.
    List<ParkingSpaceRow> findAllAdmin();
    // 민감 정보 제외 현황. 현재 유효 예약은 반환 상태에 반영한다.
    List<ParkingSpacePublicRow> findAllPublic();
    // 보정 저장 전 구획 원본을 NOWAIT 행 잠금으로 읽는다.
    ParkingSpaceRow lockForUpdate(@Param("id") Long id);
    // 상태·종류·메모 저장 건수 반환. 1건 여부는 서비스가 검사한다.
    int updateAdminSpace(@Param("id") Long id, @Param("status") String status,
                         @Param("type") String type, @Param("memo") String memo);
    // 구획의 열린 변경 이력 구간을 닫는다.
    int closeOpenHistory(@Param("id") Long id);
    // 현재 구획 스냅샷·관리자 ID·사유를 ADMIN 이력으로 저장한다.
    int insertAdminHistory(@Param("id") Long id, @Param("adminId") Long adminId,
                           @Param("reason") String reason);
    // PK로 단건 결과를 조회한다. 반환 DTO와 실제 조인은 연결 XML에서 정의한다.
    ParkingSpaceRow findById(@Param("id") Long id);
    // 구획 변경 이력 최근 30건 조회.
    List<ParkingSpaceHistoryRow> findHistory(@Param("id") Long id);
    // 현재 최신 이력 PK를 조회해 저장 기준과 비교한다.
    Long latestHistoryId(@Param("id") Long id);
    // 관리자 보정 이전의 지연 감지를 판단할 최신 보정 시각 조회.
    Timestamp latestAdminChangedAt(@Param("id") Long id);
    // 메모·사유가 기존 DB 컬럼 길이를 만족하는 항목 수를 반환한다.
    int countValidTextColumns(@Param("memo") String memo, @Param("reason") String reason);
}
