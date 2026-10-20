package kr.co.alpharking.dto.vehiclepenalty;


import java.util.Date;

import kr.co.alpharking.security.Admin;
import kr.co.alpharking.dto.vehicle.VehicleDTO;

import org.apache.ibatis.type.Alias;

import lombok.Getter;
import lombok.Setter;


@Getter
@Setter
@Alias("vhpy")
public class VehiclePenaltyDto {
	
	private Long vehiclepenaltyid; // 패널티 식별자
	private Long vehicleid; // 대상 차량
	private String violationtypecode; // 위반 유형
	private int penaltyamount; // 벌칙금
	private String reason; // 위반/패널티 사유
	private Long imposedbyadminid; // 부과 관리자
	private Date imposedat; // 부과 일시
	private String statuscode; // 패널티 처리 상태
	
	// N:1 vehicle
	private VehicleDTO vehicle;
	
	// N:1 admin
	private Admin admin;
}