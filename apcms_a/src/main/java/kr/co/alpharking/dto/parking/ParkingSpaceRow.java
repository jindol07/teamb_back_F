/** 파일 안내
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
    // PARKING_SPACE의 실제 숫자 PK. 도면 문자열 코드와 구분한다.
    private Long parkingSpaceId;
    // 도면에서 사용하는 층 번호.
    private Integer floorNo;
    // 서버가 조회한 층 표시명.
    private String floorName;
    // 구역 코드. 구획 번호와 함께 AI 공통 코드를 구성한다.
    private String zoneCode;
    // 구역 내 구획 번호. 예: 01.
    private String spaceNumber;
    // 일반·전기차·장애인 등 구획 종류 코드. 점유 상태와 별개다.
    private String spaceTypeCode;
    // DB 구획 원본 상태. 공개 현황의 예약 계산 결과와 구분하여 보정 충돌 검사에 사용한다.
    private String spaceStatusCode;
    // 640×480 기준 도면의 구획 왼쪽 위치.
    private BigDecimal xPosition;
    // 640×480 기준 도면의 구획 위쪽 위치.
    private BigDecimal yPosition;
    // 기준 도면에서 구획 가로 크기.
    private BigDecimal width;
    // 기준 도면에서 구획 세로 크기.
    private BigDecimal height;
    // AI와 화면이 공유하는 구획 코드. 예: 1F-A01.
    private String spaceCode;
    /** 관리자 전용 차량번호. 미출차 기록이 정확히 한 건 매칭될 때만 제공. */
    // 번호판 문자열. 관리자 전용 조회에서는 연결된 기존 기록을 기준으로 제공한다.
    private String vehicleNumber;
    // 관리자 메모 또는 이력 시점의 메모. 사용자 공개 DTO에는 없다.
    private String memo;
    // 서버에서 조회한 구획 수정 시각 문자열.
    private String updatedAt;
}
