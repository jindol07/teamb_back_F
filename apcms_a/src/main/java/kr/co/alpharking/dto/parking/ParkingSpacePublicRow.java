/** 파일 안내
 * 용도: A 서버에서 민감 필드를 제외한 구획 현황 응답.
 * 사용처·연결: parking-space.xml.findAllPublic → 서비스의 /public 조회 및 A ParkingWebSocketHandler.
 * 메모·차량번호를 정의하지 않는다. 같은 이름의 U record는 별도 애플리케이션의 DTO다.
 */
package kr.co.alpharking.dto.parking;

import java.math.BigDecimal;
import lombok.Data;
import org.apache.ibatis.type.Alias;

/** 사용자 공개용 DTO. 관리자 메모와 차량번호를 반환하지 않음. */
@Data
@Alias("ParkingSpacePublicRow")
public class ParkingSpacePublicRow {
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
    // 서버 구획 상태 코드. 공개 조회에서는 예약이 반영된 표시 상태일 수 있다.
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
    // 서버에서 조회한 구획 수정 시각 문자열.
    private String updatedAt;
}
