/** [1023_1010] 파일 안내
 * 용도: 관리자 구획 조회·잠금·보정에 사용하는 SQL 결과.
 * 사용처·연결: parking-space.xml, ai-parking-occupancy.xml → 관련 DAO·Service·Controller.
 * 메모·차량번호가 포함될 수 있어 사용자 공개 응답과 구분한다. 잠금 조회에서는 일부 필드만 채워질 수 있다.
 */
package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;
import lombok.Data;
import org.apache.ibatis.type.Alias;

/** 관리자 조회용 구획 DTO: FLOOR -> ZONE -> SPACE. */
@Data
@Alias("ParkingSpaceRow")
public class ParkingSpaceRow {
    // [1023_1010] PARKING_SPACE의 실제 숫자 PK. 도면 문자열 코드와 구분한다.
    private Long parkingSpaceId;
    // [1023_1010] 도면에서 사용하는 층 번호.
    private Integer floorNo;
    // [1023_1010] 서버가 조회한 층 표시명.
    private String floorName;
    // [1023_1010] 구역 코드. 구획 번호와 함께 AI 공통 코드를 구성한다.
    private String zoneCode;
    // [1023_1010] 구역 내 구획 번호. 예: 01.
    private String spaceNumber;
    // [1023_1010] 일반·전기차·장애인 등 구획 종류 코드. 점유 상태와 별개다.
    private String spaceTypeCode;
    // [1023_1010] 서버 구획 상태 코드. 공개 조회에서는 예약이 반영된 표시 상태일 수 있다.
    private String spaceStatusCode;
    // [1023_1010] 640×480 기준 도면의 구획 왼쪽 위치.
    private BigDecimal xPosition;
    // [1023_1010] 640×480 기준 도면의 구획 위쪽 위치.
    private BigDecimal yPosition;
    // [1023_1010] 기준 도면에서 구획 가로 크기.
    private BigDecimal width;
    // [1023_1010] 기준 도면에서 구획 세로 크기.
    private BigDecimal height;
    // [1023_1010] AI와 화면이 공유하는 구획 코드. 예: 1F-A01.
    private String spaceCode;
    /** 관리자 전용 차량번호. 미출차 기록이 정확히 한 건 매칭될 때만 제공. */
    // [1023_1010] 번호판 문자열. 관리자 전용 조회에서는 연결된 기존 기록을 기준으로 제공한다.
    private String vehicleNumber;
    // [1023_1010] 관리자 메모 또는 이력 시점의 메모. 사용자 공개 DTO에는 없다.
    private String memo;
    // [1023_1010] 서버에서 조회한 구획 수정 시각 문자열.
    private String updatedAt;
}
