package kr.co.alpharking.dto.auth;

import java.time.LocalDateTime;
import java.util.List;

import kr.co.alpharking.security.SignupVehicle;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class SignupRequest {
	private String username;
	private String password;
	private String password_confirm;
	private String email;
	private String email_code;
	private String phone;
	private Long floor_no;
	private Long company_id;
	private String office_number;
	private String verification_code;
	
	private List<SignupVehicle> vehicle_list;
	
	private Long company_company_id;
	private String company_company_name;
	private String company_business_number;
	private String company_status_code;
	private LocalDateTime company_created_at;
	private LocalDateTime company_updated_at;
	private LocalDateTime company_deleted_at;
	private String company_company_addr;
}
	