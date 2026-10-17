package kr.co.alpharking.entity.reservation;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Entity
@Table(name = "PARKING_RESERVATION")
public class ParkingReservation {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "parking_reservation_seq")
    @SequenceGenerator(
        name = "parking_reservation_seq",
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

    @Column(name = "VEHICLE_NUMBER", nullable = false, length = 50)
    private String vehicleNumber;

    @Column(name = "RESERVATION_TYPE_CODE", nullable = false, length = 50)
    private String reservationTypeCode;

    @Column(name = "RESERVATION_START_AT", nullable = false)
    private LocalDateTime reservationStartAt;

    @Column(name = "RESERVATION_END_AT", nullable = false)
    private LocalDateTime reservationEndAt;

    @Column(name = "STATUS_CODE", nullable = false, length = 50)
    private String statusCode;

    @Column(name = "RECOMMENDED_YN", nullable = false, length = 1)
    private String recommendedYn = "N";

    @Column(name = "CREATED_AT", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "UPDATED_AT", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "CANCELLED_AT")
    private LocalDateTime cancelledAt;

    @PrePersist
    protected void onCreate() {
        LocalDateTime now = LocalDateTime.now();

        if (createdAt == null) {
            createdAt = now;
        }
        if (updatedAt == null) {
            updatedAt = now;
        }
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}