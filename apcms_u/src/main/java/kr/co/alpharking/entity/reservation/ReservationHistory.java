package kr.co.alpharking.entity.reservation;

import java.time.LocalDateTime;

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
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "PARKING_RESERVATION_HISTORY")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ReservationHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "seq_parking_reservation_history_gen")
    @SequenceGenerator(
            name = "seq_parking_reservation_history_gen",
            sequenceName = "SEQ_PARKING_RESERVATION_HISTORY",
            allocationSize = 1
    )
    @Column(name = "PARKING_RESERVATION_HISTORY_ID")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "PARKING_RESERVATION_ID", nullable = false)
    private Reservation reservation;

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
    private String recommendedYn;

    @Column(name = "CREATED_AT", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "UPDATED_AT", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "CANCELLED_AT")
    private LocalDateTime cancelledAt;

    @Column(name = "CHANGED_BY_ADMIN_ID")
    private Long changedByAdminId;

    @Column(name = "ACTOR_TYPE_CODE", nullable = false, length = 20)
    private String actorTypeCode;

    @Column(name = "ACTOR_ID")
    private Long actorId;

    @Column(name = "CHANGE_TYPE_CODE", nullable = false, length = 20)
    private String changeTypeCode;

    @Column(name = "CHANGE_REASON", length = 500)
    private String changeReason;

    @Column(name = "VALID_FROM", nullable = false)
    private LocalDateTime validFrom;

    @Column(name = "VALID_TO")
    private LocalDateTime validTo;

    // 예약 정보를 복사하여 이력 생성
    public static ReservationHistory create(
            Reservation reservation,
            String actorTypeCode,
            Long actorId,
            String changeTypeCode,
            String changeReason,
            LocalDateTime validFrom) {

        ReservationHistory history = new ReservationHistory();

        history.reservation = reservation;
        history.officeId = reservation.getOfficeId();
        history.parkingSpaceId = reservation.getParkingSpaceId();
        history.vehicleId = reservation.getVehicleId();
        history.vehicleNumber = reservation.getVehicleNumber();
        history.reservationTypeCode = reservation.getReservationTypeCode();
        history.reservationStartAt = reservation.getReservationStartAt();
        history.reservationEndAt = reservation.getReservationEndAt();
        history.statusCode = reservation.getStatusCode();
        history.recommendedYn = reservation.getRecommendedYn();
        history.createdAt = reservation.getCreatedAt();
        history.updatedAt = reservation.getUpdatedAt();
        history.cancelledAt = reservation.getCancelledAt();

        history.actorTypeCode = actorTypeCode;
        history.actorId = actorId;
        history.changeTypeCode = changeTypeCode;
        history.changeReason = changeReason;
        history.validFrom = validFrom;
        history.validTo = null;

        return history;
    }
}