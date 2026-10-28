/** 파일 안내
 * 용도: 대시보드 최근 입출차 목록의 이벤트 한 행.
 * 직접 사용처: dashboard.xml.findRecentParkingEvents → DashboardController → ParkingUsagePanel.
 * 하나의 이용 기록이 입차·출차 두 행으로 나타날 수 있어 이벤트 종류와 함께 식별한다.
 * 구획은 이용 기록에 현재 연결된 정보이며 이벤트 발생 당시 위치를 별도로 보관한 값은 아니다.
 */
package kr.co.alpharking.dto.dashboard;

import org.apache.ibatis.type.Alias;
import lombok.Data;

/** dashboard.xml → ParkingUsagePanel. 같은 이용 기록의 입차·출차를 각각 한 행으로 반환한다. */
@Data
@Alias("DashboardParkingEventRow")
public class DashboardParkingEventRow {
    /** PARKING_USAGE의 PK. 입차·출차 행이 같은 값을 공유할 수 있다. */
    private Long parkingUsageId;
    /** 해당 이용 기록에 저장된 차량번호. */
    private String vehicleNumber;
    /** ENTRY 또는 EXIT. */
    private String eventType;
    /** 선택된 입차 또는 출차 시각을 시간대 없는 ISO 형태로 표현한 문자열. */
    private String occurredAt;
    /** 연결된 구획 코드. 구획 미연결이면 null이다. */
    private String spaceCode;
}
