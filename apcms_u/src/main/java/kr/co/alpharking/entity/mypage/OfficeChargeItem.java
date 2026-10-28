package kr.co.alpharking.entity.mypage;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;

@Entity
@Table(name = "OFFICE_CHARGE_ITEM")
@Immutable
@Getter
@NoArgsConstructor
public class OfficeChargeItem {
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "mypage_office_charge_item_seq")
    @SequenceGenerator(name = "mypage_office_charge_item_seq", sequenceName = "seq_office_charge_item", allocationSize = 1)
    @Column(name = "OFFICE_CHARGE_ITEM_ID")
    private Long id;
    @Column(name = "OFFICE_CHARGE_ID", nullable = false)
    private Long chargeId;
    @Column(name = "CHARGE_TYPE_CODE", length = 50, nullable = false)
    private String chargeTypeCode;
    @Column(name = "REFERENCE_ID")
    private Long referenceId;
    @Column(name = "AMOUNT", precision = 12, scale = 2, nullable = false)
    private BigDecimal amount;
    @Column(name = "DESCRIPTION", length = 500)
    private String description;
    @Column(name = "CREATED_AT", nullable = false)
    private LocalDateTime createdAt;

    // 패널티 식별자를 참조하는 청구 상세를 만들어 중복 반영 여부를 추적한다.
    public static OfficeChargeItem forPenalty(Long chargeId, VehiclePenalty penalty, LocalDateTime now) {
        OfficeChargeItem item = new OfficeChargeItem();
        item.chargeId = chargeId;
        item.chargeTypeCode = "PENALTY";
        item.referenceId = penalty.getId();
        item.amount = penalty.getAmount();
        item.description = "차량 패널티 #" + penalty.getId();
        item.createdAt = now;
        return item;
    }
}
