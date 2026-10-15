package kr.co.alpharking.entity.vehicle;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.time.LocalDateTime;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@Entity
@Table(name = "FAVORITE_VISITOR_VEHICLE")
public class FavoriteVisitorVehicle {

    @Id
    @GeneratedValue(
        strategy = GenerationType.SEQUENCE,
        generator = "favorite_visitor_vehicle_seq"
    )
    @SequenceGenerator(
        name = "favorite_visitor_vehicle_seq",
        sequenceName = "SEQ_FAVORITE_VISITOR_VEHICLE",
        allocationSize = 1
    )
    @Column(name = "FAVORITE_VISITOR_VEHICLE_ID")
    private Long favoriteVisitorVehicleId;

    // OFFICE_ID (NOT NULL)
    // Office 엔티티가 확정되면 추후 @ManyToOne으로 변경 가능
    @Column(name = "OFFICE_ID", nullable = false)
    private Long officeId;

    // VEHICLE_NUMBER (NOT NULL, VARCHAR2(50))
    @Column(name = "VEHICLE_NUMBER", nullable = false, length = 50)
    private String vehicleNumber;

    // ALIAS_NAME (NULL 허용, VARCHAR2(50))
    @Column(name = "ALIAS_NAME", length = 50)
    private String aliasName;

    // CREATED_AT (NOT NULL)
    @Column(name = "CREATED_AT", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    public void prePersist() {
        if (this.createdAt == null) {
            this.createdAt = LocalDateTime.now();
        }
    }
}