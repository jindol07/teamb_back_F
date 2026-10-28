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

@Entity
@Table(name = "OFFICE_CHARGE")
@Getter
@NoArgsConstructor
public class OfficeCharge {
    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "mypage_office_charge_seq")
    @SequenceGenerator(name = "mypage_office_charge_seq", sequenceName = "seq_office_charge", allocationSize = 1)
    @Column(name = "OFFICE_CHARGE_ID")
    private Long id;
    @Column(name = "OFFICE_ID", nullable = false)
    private Long officeId;
    @Column(name = "CHARGE_YEAR_MONTH", columnDefinition = "CHAR(6)", nullable = false)
    private String yearMonth;
    @Column(name = "TOTAL_AMOUNT", precision = 12, scale = 2, nullable = false)
    private BigDecimal totalAmount;
    @Column(name = "MILEAGE_DISCOUNT_AMOUNT", precision = 12, scale = 2, nullable = false)
    private BigDecimal mileageDiscountAmount;
    @Column(name = "FINAL_AMOUNT", precision = 12, scale = 2, nullable = false)
    private BigDecimal finalAmount;
    @Column(name = "STATUS_CODE", length = 50, nullable = false)
    private String statusCode;
    @Column(name = "CREATED_AT", nullable = false)
    private LocalDateTime createdAt;

    // 미반영 패널티를 청구할 사무실·연월의 신규 청구를 생성한다.
    public static OfficeCharge forPenalty(Long officeId, String yearMonth, LocalDateTime now) {
        OfficeCharge charge = new OfficeCharge();
        charge.officeId = officeId;
        charge.yearMonth = yearMonth;
        charge.totalAmount = BigDecimal.ZERO;
        charge.mileageDiscountAmount = BigDecimal.ZERO;
        charge.finalAmount = BigDecimal.ZERO;
        charge.statusCode = "BILLED";
        charge.createdAt = now;
        return charge;
    }

    // 패널티 금액을 청구 합계에 더하고 기존 누적 마일리지 할인을 보존한다.
    public void addPenalty(BigDecimal amount) {
        totalAmount = totalAmount.add(amount);
        finalAmount = totalAmount.subtract(mileageDiscountAmount);
    }

    // 누적 마일리지 할인액과 최종 관리비를 갱신하고 전액 차감이면 납부 완료로 바꾼다.
    public void applyMileage(BigDecimal amount) {
        mileageDiscountAmount = mileageDiscountAmount.add(amount);
        finalAmount = totalAmount.subtract(mileageDiscountAmount);
        if (finalAmount.signum() == 0) statusCode = "PAID";
    }
}
