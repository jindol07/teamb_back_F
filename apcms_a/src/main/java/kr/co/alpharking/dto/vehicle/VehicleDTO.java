package kr.co.alpharking.dto.vehicle;

// 날짜 형태: 2026-10-15 11:30:00
// 한국 시간대 기준으로 처리
import java.util.Date;

import org.apache.ibatis.type.Alias;

import com.fasterxml.jackson.annotation.JsonFormat;

import lombok.Getter;
import lombok.Setter;

@Alias("vhdto")
@Getter
@Setter
public class VehicleDTO {

    private Long vehicleid; // 차량 식별자
    private Long officeid; // 소속 사무실 식별자
    private String officenumber; // 호수 정보

    private String vehiclenumber; // 차량번호
    private String vehiclemodel; // 차량모델
    private String ownername; // 차주명

    private String vehicletypecode; // PERSONAL / OFFICE
    private String registrationtypecode; // INITIAL / ADDITIONAL
    private String registrationstatuscode; // REQUESTED / REGISTERED / REJECTED

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd HH:mm:ss", timezone = "Asia/Seoul")
    private String registeredat; // 관리자 승인/등록 완료 일시

    private String rejectedreason; // 반려 사유

    @JsonFormat(shape = JsonFormat.Shape.STRING,pattern = "yyyy-MM-dd HH:mm:ss",timezone = "Asia/Seoul")
    private Date createdat; // 생성일시

    @JsonFormat(shape = JsonFormat.Shape.STRING,pattern = "yyyy-MM-dd HH:mm:ss",timezone = "Asia/Seoul")
    private Date updatedat; // 수정일시

    @JsonFormat(shape = JsonFormat.Shape.STRING,pattern = "yyyy-MM-dd HH:mm:ss",timezone = "Asia/Seoul")
    private Date deletedat; // 소프트 삭제 일시

    // N:1 office
    // private Office office;

    // 1:N vehicle_penalty
    // private List<VehiclePenalty> vehiclepenaltyList;

    // 1:N parking_usage
    // private List<ParkingUsage> parkingusageList;

    // 1:N recommendation_log
    // private List<RecommendationLog> recommendationlogList;
}