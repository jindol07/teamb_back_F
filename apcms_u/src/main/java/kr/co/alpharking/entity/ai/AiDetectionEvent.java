package kr.co.alpharking.entity.ai;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.Data;

@Data
@Entity
@Table(name = "AI_DETECTION_EVENT")
public class AiDetectionEvent {

	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "aiDetectionEventSeq")
	@SequenceGenerator(name = "aiDetectionEventSeq", sequenceName = "SEQ_AI_DETECTION_EVENT", allocationSize = 1)
	@Column(name = "AI_DETECTION_EVENT_ID")
	private Long aiDetectionEventId;

	@Column(name = "PARKING_SPACE_ID")
	private Long parkingSpaceId;

	@Column(name = "DETECTED_VEHICLE_NUMBER", length = 50)
	private String detectedVehicleNumber;
	
//	현재 신뢰도와 좌표값은 FastAPI 응답에는 포함되지만
//	JPA 매핑 문제 때문에 일부 컬럼 저장은 보류하고
//	RAW_PAYLOAD에 JSON 형태로 원본 결과를 저장하고 있음
	
//	@Column(name = "VEHICLE_CONFIDENCE")
//	private Double vehicleConfidence;
//
//	@Column(name = "PLATE_CONFIDENCE")
//	private Double plateConfidence;
//
//	@Column(name = "DETECTED_X")
//	private Double detectedX;
//
//	@Column(name = "DETECTED_Y")
//	private Double detectedY;
	
	@Column(name = "DETECTED_AT", nullable = false)
	private LocalDateTime detectedAt;

	@Column(name = "CREATED_AT", nullable = false)
	private LocalDateTime createdAt;
	
	@Lob
	@Column(name = "RAW_PAYLOAD")
	private String rawPayload;
}