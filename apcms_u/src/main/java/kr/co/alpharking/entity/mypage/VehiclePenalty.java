package kr.co.alpharking.entity.mypage;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;

@Entity(name = "MyPageVehiclePenalty")
@Table(name = "VEHICLE_PENALTY")
@Immutable
@Getter
@NoArgsConstructor
public class VehiclePenalty {
    @Id
    @Column(name = "VEHICLE_PENALTY_ID")
    private Long id;
    @Column(name = "VEHICLE_ID")
    private Long vehicleId;
    @Column(name = "VIOLATION_TYPE_CODE", length = 50)
    private String violationTypeCode;
    @Column(name = "PENALTY_AMOUNT")
    private BigDecimal amount;
    @Lob
    @Column(name = "REASON")
    private String reason;
    @Column(name = "IMPOSED_AT")
    private LocalDateTime imposedAt;
}
