package kr.co.alpharking.dto.dashboard;

import org.apache.ibatis.type.Alias;
import lombok.Data;

/** dashboard.xml → ParkingUsagePanel. 같은 이용 기록의 입차·출차를 각각 한 행으로 반환한다. */
@Data
@Alias("DashboardParkingEventRow")
public class DashboardParkingEventRow {
    private Long parkingUsageId;
    private String vehicleNumber;
    private String eventType;
    private String occurredAt;
    private String spaceCode;
}
