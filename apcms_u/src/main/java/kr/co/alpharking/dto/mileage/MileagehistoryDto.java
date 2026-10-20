package kr.co.alpharking.dto.mileage;

import java.util.Date;

import com.fasterxml.jackson.annotation.JsonFormat;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import kr.co.alpharking.security.Office;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Table(name = "mileage_history")
@Entity
@Getter
@Setter
@NoArgsConstructor
public class MileagehistoryDto {

	@Id
	@Column(name = "mileage_history_id")
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "mileage_history_seq")
	@SequenceGenerator(name = "mileage_history_seq", sequenceName = "seq_mileage_history", allocationSize = 1)
	private Long mileagehistoryid; // 마일리지 이력 식별자
	@Column(name = "mileage_type_code")
	private String mileagetypecode; // REPORT_REWARD/ON_TIME_EXIT_REWARD/USE
	@Column(name = "amount")
	private Long amount; // 적립은 양수, 사용은 음수 권장
	@Column(name = "reference_type_code")
	private String referencetypecode; // 원인 업무 유형
	@Column(name = "reference_id")
	private Long referenceid; // 원인 업무 PK
	@Column(name = "description")
	private String description; // 설명

	@Column(name = "created_at")
	@JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd HH:mm:ss", timezone = "Asia/Seoul")
	private Date createdat; // 발생 일시

	// N : 1 관계 office
	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "office_id", nullable = false)
	private Office office;
}