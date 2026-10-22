package kr.co.alpharking.security;

import java.sql.Date;
import java.time.LocalDateTime;

import org.springframework.security.core.userdetails.UserDetails;

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
@Table(name = "COMPANY")
public class Company {
	@Id
	@SequenceGenerator(
	    name = "seq_company",          // @GeneratedValue에서 참조할 생성기 이름
	    sequenceName = "SEQ_COMPANY",  // 실제 Oracle 시퀀스 이름인지 확인
	    allocationSize = 1            // DB 시퀀스의 증가 크기와 맞춤
	)
	@GeneratedValue(
	    strategy = GenerationType.SEQUENCE,
	    generator = "seq_company"
	)
	private Long company_id;
	private String company_name;
	private String business_number;
	private String status_code;
	private LocalDateTime created_at;
	private LocalDateTime updated_at;
	private LocalDateTime deleted_at;
	private String company_addr;
	
	
}
