package kr.co.alpharking.dto.vehicle;

import java.util.Date;

import org.apache.ibatis.type.Alias;

import com.fasterxml.jackson.annotation.JsonFormat;

import lombok.Getter;
import lombok.Setter;

@Alias("vcrdto")
@Getter
@Setter
public class VehicleChangeRequestDTO {
    private Long vehiclechangerequestid;       // 차량 변경 요청 ID
    private Long officeid;                    // 지사 ID
    private String officenumber;			
    private Long targetvehicleid;             // 대상 차량 ID
    private String requesttypecode;           // 요청 유형 코드 (ADD, UPDATE, DELETE)
    private String requestedvehiclenumber;    // 요청된 차량 번호
    private String requestedvehiclemodel;     // 요청된 차량 모델
    private String requestedownername;        // 요청된 소유자 이름
    private String requestedvehicletypecode;  // 요청된 차량 유형 코드
    private String requestreason;             // 요청 사유
    private String requeststatuscode;         // 요청 상태 코드 (REQUESTED, APPROVED, REJECTED, CANCELLED)
    private Long revieweradminid;             // 검토자 관리자 ID
    private String reviewreason;             // 검토 사유
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd HH:mm:ss", timezone = "Asia/Seoul")
    private Date requestedat;        // 요청 일시
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd HH:mm:ss", timezone = "Asia/Seoul")
    private Date reviewedat;         // 검토 일시
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd HH:mm:ss", timezone = "Asia/Seoul")
    private Date appliedat;          // 적용 일시
}