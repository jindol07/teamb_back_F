package kr.co.alpharking.security;

import java.time.LocalDateTime;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "VEHICLE")
public class SignupVehicle {
	@Id
	@SequenceGenerator(
	    name = "seq_vehicle",          // @GeneratedValue에서 참조할 생성기 이름
	    sequenceName = "SEQ_VEHICLE",  // 실제 Oracle 시퀀스 이름인지 확인
	    allocationSize = 1            // DB 시퀀스의 증가 크기와 맞춤
	)
	@GeneratedValue(
	    strategy = GenerationType.SEQUENCE,
	    generator = "seq_vehicle"
	)
	private Long vehicle_id;
	private Long office_id;
	private String vehicle_number;
	private String vehicle_model;
	private String owner_name;
	private String vehicle_type_code;
	private String registration_type_code;
	private String registration_status_code;
	private LocalDateTime registered_at;
	private String rejected_reason;
	private LocalDateTime created_at;
	private LocalDateTime updated_at;
	private LocalDateTime deleted_at;
}
