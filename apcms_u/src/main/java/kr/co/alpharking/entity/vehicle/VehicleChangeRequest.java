package kr.co.alpharking.entity.vehicle;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(name = "VEHICLE_CHANGE_REQUEST")
public class VehicleChangeRequest {
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "vehicle_change_request_seq")
    @SequenceGenerator(name = "vehicle_change_request_seq", sequenceName = "SEQ_VCHANGE_REQ", allocationSize = 1)
    @Column(name = "VEHICLE_CHANGE_REQUEST_ID")
    private Long vehicleChangeRequestId;

    @Column(name = "OFFICE_ID", nullable = false)
    private Long officeId;

    @Column(name = "REQUEST_TYPE_CODE", nullable = false)
    private String requestTypeCode;

    @Column(name = "REQUESTED_VEHICLE_NUMBER", nullable = false)
    private String requestedVehicleNumber;

    @Column(name = "REQUESTED_VEHICLE_MODEL")
    private String requestedVehicleModel;

    @Column(name = "REQUESTED_OWNER_NAME")
    private String requestedOwnerName;

    @Column(name = "REQUESTED_VEHICLE_TYPE_CODE")
    private String requestedVehicleTypeCode;

    @Column(name = "REQUEST_REASON")
    private String requestReason;

    @Column(name = "REQUEST_STATUS_CODE", nullable = false)
    private String requestStatusCode;

    @Column(name = "REQUESTED_AT")
    private LocalDateTime requestedAt;
}
