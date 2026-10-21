package kr.co.alpharking.recmnTest;

import java.time.LocalDate;

import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class ParkingRecommendationRequest {

    // 예약 시작일, 프론트에서 YYYY-MM-DD 형식으로 전달
    @NotNull
    private LocalDate startDate;

    // 예약 종료일, 프론트에서 YYYY-MM-DD 형식으로 전달
    @NotNull
    private LocalDate endDate;
}
