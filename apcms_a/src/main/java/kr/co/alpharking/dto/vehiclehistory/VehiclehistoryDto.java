package kr.co.alpharking.dto.vehiclehistory;

import java.util.Date;

import org.apache.ibatis.type.Alias;

import lombok.Getter;
import lombok.Setter;

@Alias("history")
@Getter
@Setter
public class VehiclehistoryDto {

    private Long vehiclehistoryid;          // 차량 이력 식별자
    private Long vehicleid;                 // 차량 식별자
    private Long officeid;                  // 소속 사무실 식별자
    private String vehiclenumber;           // 차량 번호
    private String vehiclemodel;            // 차량 모델
    private String ownername;               // 차주명
    private String vehicletypecode;         // 차량 유형 코드 (PERSONAL / OFFICE)
    private String registrationtypecode;    // 등록 유형 코드 (INITIAL / ADDITIONAL)
    private String registrationstatuscode;  // 등록 상태 코드 (REQUESTED / REGISTERED / REJECTED)
    private Date registeredat;              // 차량 등록 완료 일시
    private String rejectedreason;          // 등록 반려 사유
    private Date createdat;                 // 차량 정보 생성 일시
    private Date updatedat;                 // 차량 정보 최종 수정 일시
    private Date deletedat;                 // 차량 삭제 일시 (논리 삭제)
    private Long changedbyadminid;          // 작업을 수행한 관리자 ID (관리자 작업 시)
    private String actortypecode;           // 작업자 유형 (ADMIN / USER / SYSTEM)
    private Long actorid;                   // 작업자 ID (ADMIN은 admin_id, USER는 office_id, SYSTEM은 NULL)
    private String changetypecode;          // 변경 유형 (INSERT / UPDATE / DELETE / APPROVE / REJECT / CANCEL / CORRECT)
    private String changereason;            // 변경 사유 또는 검토 사유
    private Date validfrom;                 // 이력 버전의 유효 시작 시각
    private Date validto;                   // 이력 버전의 유효 종료 시각 (현재 최신 이력은 NULL)
}