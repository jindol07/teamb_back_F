package kr.co.alpharking.entity.vehicle;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;

@Data
@Entity
@Table(name = "VEHICLE")
public class Vehicle {

	@Id
	@Column(name = "VEHICLE_ID")
	private Long vehicleId;

	@Column(name = "OFFICE_ID", nullable = false)
	private Long officeId;

	@Column(name = "VEHICLE_NUMBER", nullable = false)
	private String vehicleNumber;

	@Column(name = "VEHICLE_MODEL")
	private String vehicleModel;

	@Column(name = "OWNER_NAME")
	private String ownerName;

	@Column(name = "VEHICLE_TYPE_CODE")
	private String vehicleTypeCode;

	@Column(name = "REGISTRATION_TYPE_CODE")
	private String registrationTypeCode;

	@Column(name = "REGISTRATION_STATUS_CODE")
	private String registrationStatusCode;

	@Column(name = "REGISTERED_AT")
	private LocalDateTime registeredAt;

	@Column(name = "REJECTED_REASON")
	private String rejectedReason;

	@Column(name = "CREATED_AT")
	private LocalDateTime createdAt;

	@Column(name = "UPDATED_AT")
	private LocalDateTime updatedAt;

	@Column(name = "DELETED_AT")
	private LocalDateTime deletedAt;
}