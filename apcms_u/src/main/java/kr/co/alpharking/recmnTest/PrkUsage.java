
package kr.co.alpharking.recmnTest;

import java.math.BigDecimal;
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
import lombok.NoArgsConstructor;

@Entity
@Getter
@Setter
@NoArgsConstructor
@Table(name = "PARKING_USAGE")
public class PrkUsage {

    // 주차이력 PK
    @Id
    @GeneratedValue(
        strategy = GenerationType.SEQUENCE,
        generator = "seq_parking_usage_gen"
    )
    @SequenceGenerator(
        name = "seq_parking_usage_gen",
        sequenceName = "seq_parking_usage",
        allocationSize = 1
    )
    @Column(name = "PARKING_USAGE_ID", nullable = false)
    private Long parkingUsageId;

    // 사용자 ID
    @Column(name = "OFFICE_ID", nullable = false)
    private Long officeId;

    // 차량 ID (NULL 허용)
    @Column(name = "VEHICLE_ID")
    private Long vehicleId;

    // 주차면 ID (NULL 허용)
    @Column(name = "PARKING_SPACE_ID")
    private Long parkingSpaceId;

    // 주차예약 ID (NULL 허용)
    @Column(name = "PARKING_RESERVATION_ID")
    private Long parkingReservationId;

    // 차량번호
    @Column(name = "VEHICLE_NUMBER", length = 50, nullable = false)
    private String vehicleNumber;

    // 주차유형 코드
    @Column(name = "PARKING_TYPE_CODE", length = 50, nullable = false)
    private String parkingTypeCode;

    // 입차 일시
    @Column(name = "ENTRY_AT", nullable = false)
    private LocalDateTime entryAt;

    // 출차 일시 (NULL 허용)
    @Column(name = "EXIT_AT")
    private LocalDateTime exitAt;

    // 주차요금
    @Column(
        name = "CHARGE_AMOUNT",
        precision = 12,
        scale = 2,
        nullable = false
    )
    private BigDecimal chargeAmount;

    // 생성 일시
    @Column(name = "CREATED_AT", nullable = false)
    private LocalDateTime createdAt;
}
