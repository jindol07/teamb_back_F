package kr.co.alpharking.entity.reservation;

import java.time.LocalDateTime;

import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Getter
@Setter
@NoArgsConstructor
@Table(name = "PARKING_RESERVATION")
public class Reservation {
	
	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "seq_parking_reservation_gen")
	@SequenceGenerator(
			name = "seq_parking_reservation_gen",
			sequenceName = "SEQ_PARKING_RESERVATION",
			allocationSize = 1
	)
	@Column(name = "PARKING_RESERVATION_ID")
    private Long parkingReservationId;

    @Column(name = "OFFICE_ID", nullable = false)
    private Long officeId;

    @Column(name = "PARKING_SPACE_ID", nullable = false)
    private Long parkingSpaceId;

    @Column(name = "VEHICLE_ID")
    private Long vehicleId;

    @Column(name = "VEHICLE_NUMBER", length = 50, nullable = false)
    private String vehicleNumber;

    @Column(name = "RESERVATION_TYPE_CODE", length = 50, nullable = false)
    private String reservationTypeCode;

    @Column(name = "RESERVATION_START_AT", nullable = false)
    private LocalDateTime reservationStartAt;

    @Column(name = "RESERVATION_END_AT", nullable = false)
    private LocalDateTime reservationEndAt;

    @Column(name = "STATUS_CODE", length = 50, nullable = false)
    private String statusCode;

    @Column(name = "RECOMMENDED_YN", length = 1, nullable = false)
    private String recommendedYn = "N";

    @CreationTimestamp
    @Column(name = "CREATED_AT", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "UPDATED_AT", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "CANCELLED_AT")
    private LocalDateTime cancelledAt;
}