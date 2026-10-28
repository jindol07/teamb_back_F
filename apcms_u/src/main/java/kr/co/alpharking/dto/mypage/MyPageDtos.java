package kr.co.alpharking.dto.mypage;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public final class MyPageDtos {
    // 요청·응답 DTO 모음 클래스의 직접 생성을 방지한다.
    private MyPageDtos() {}

    public record MileageUseRequest(@NotNull @Min(1000) Long amount,
            @NotNull @DecimalMin("0") BigDecimal expectedDiscountAmount) {}
    public record PasswordChangeRequest(@NotBlank String currentPassword,
            @NotBlank @Size(min = 8, max = 20) String newPassword,
            @NotBlank String confirmPassword) {}
    public record WithdrawRequest(@NotBlank String currentPassword, @NotBlank String confirmation) {}
    public record ChargesResponse(String yearMonth, BigDecimal mileageBalance, List<ChargeResponse> charges) {}
    public record ChargeResponse(Long id, String yearMonth, BigDecimal totalAmount,
            BigDecimal mileageDiscountAmount, BigDecimal finalAmount, String statusCode,
            String statusName, List<ChargeItemResponse> items) {}
    public record ChargeItemResponse(Long id, String typeName, BigDecimal amount, String description) {}
    public record ParkingUsageResponse(Long id, String vehicleNumber, LocalDateTime entryAt,
            LocalDateTime exitAt, String parkingTypeName) {}
    public record AcceptedReportResponse(Long id, String vehicleNumber, String typeName,
            String statusName, String reviewReason, LocalDateTime createdAt, LocalDateTime reviewedAt) {}
    public record PenaltyResponse(Long id, String vehicleNumber, String typeName,
            BigDecimal penaltyAmount, String reason, LocalDateTime imposedAt) {}

    public interface PenaltyRow {
        // 실제 부과된 패널티의 식별자를 반환한다.
        Long getId();
        // 패널티 대상 차량번호를 반환한다.
        String getVehicleNumber();
        // 공통코드에서 조회한 위반 유형명을 반환한다.
        String getTypeName();
        // 관리자가 부과한 위반 금액을 반환한다.
        BigDecimal getPenaltyAmount();
        // 관리자가 입력한 패널티 부과 사유를 반환한다.
        String getReason();
        // 패널티가 부과된 시각을 반환한다.
        LocalDateTime getImposedAt();
    }

    public interface ChargeRow {
        // 조회 결과의 업무 식별자를 반환한다.
        Long getId();
        // 조회한 관리비의 청구 연월을 반환한다.
        String getYearMonth();
        // 마일리지 할인 전 관리비 합계를 반환한다.
        BigDecimal getTotalAmount();
        // 관리비에 누적 적용된 마일리지 할인액을 반환한다.
        BigDecimal getMileageDiscountAmount();
        // 누적 마일리지 할인을 차감한 최종 관리비를 반환한다.
        BigDecimal getFinalAmount();
        // 업무 검증에 사용하는 원본 청구 상태 코드를 반환한다.
        String getStatusCode();
        // 공통코드 조인으로 조회한 사용자 표시용 상태명을 반환한다.
        String getStatusName();
    }
    public interface ChargeItemRow {
        // 조회 결과의 업무 식별자를 반환한다.
        Long getId();
        // 상세 항목이 속한 관리비 청구 식별자를 반환한다.
        Long getChargeId();
        // 공통코드 조인으로 조회한 사용자 표시용 유형명을 반환한다.
        String getTypeName();
        // 청구 상세 항목의 금액을 반환한다.
        BigDecimal getAmount();
        // 청구 상세 항목의 설명을 반환한다.
        String getDescription();
    }
    public interface ParkingUsageRow {
        // 조회 결과의 업무 식별자를 반환한다.
        Long getId();
        // 이용 또는 승인 신고 대상 차량번호를 반환한다.
        String getVehicleNumber();
        // 주차 이용의 입차 시각을 반환한다.
        LocalDateTime getEntryAt();
        // 주차 이용의 출차 시각을 반환하며 주차 중이면 null을 반환한다.
        LocalDateTime getExitAt();
        // 공통코드 조인으로 조회한 주차 이용 유형명을 반환한다.
        String getParkingTypeName();
    }
    public interface AcceptedReportRow {
        // 조회 결과의 업무 식별자를 반환한다.
        Long getId();
        // 이용 또는 승인 신고 대상 차량번호를 반환한다.
        String getVehicleNumber();
        // 공통코드 조인으로 조회한 사용자 표시용 유형명을 반환한다.
        String getTypeName();
        // 공통코드 조인으로 조회한 사용자 표시용 상태명을 반환한다.
        String getStatusName();
        // 관리자가 기록한 신고 검토 사유를 반환한다.
        String getReviewReason();
        // 신고가 접수된 시각을 반환한다.
        LocalDateTime getCreatedAt();
        // 관리자가 신고를 검토한 시각을 반환한다.
        LocalDateTime getReviewedAt();
    }
}
