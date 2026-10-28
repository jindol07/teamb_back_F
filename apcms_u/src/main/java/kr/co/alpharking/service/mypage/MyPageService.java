package kr.co.alpharking.service.mypage;

import java.math.BigDecimal;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.mileage.MileagehistoryDto;
import kr.co.alpharking.dto.mypage.MyPageDtos.*;
import kr.co.alpharking.entity.mypage.OfficeCharge;
import kr.co.alpharking.repository.mypage.*;
import kr.co.alpharking.security.Office;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MyPageService {
    private final MyPageOfficeRepository offices;
    private final OfficeChargeRepository charges;
    private final OfficeChargeItemRepository items;
    private final MyPageMileageRepository mileage;
    private final MyPageParkingUsageRepository usages;
    private final MyPageReportRepository reports;
    private final MyPagePenaltyService penalties;

    // 미반영 패널티를 반영한 뒤 당월 청구와 최신 마일리지 잔액을 반환한다.
    @Transactional
    public ChargesResponse synchronizePenalties(Long officeId) {
        penalties.synchronize(officeId);
        return currentCharges(officeId);
    }

    // 본인 차량에 실제 부과된 위반 금액과 상세 내역을 페이지로 반환한다.
    public Page<PenaltyResponse> penalties(Long officeId, int page, int size) {
        return penalties.findOwned(officeId, page, size);
    }

    // 본인 사무실의 당월 관리비·상세 항목·공통코드 표시명과 마일리지 잔액을 조회한다.
    public ChargesResponse currentCharges(Long officeId) {
        String month = currentMonth();
        List<ChargeRow> rows = charges.findCurrent(officeId, month);
        Map<Long, List<ChargeItemResponse>> details = rows.isEmpty() ? Map.of()
                : items.findCurrent(officeId, month).stream().collect(Collectors.groupingBy(
                        ChargeItemRow::getChargeId, Collectors.mapping(i -> new ChargeItemResponse(
                                i.getId(), name(i.getTypeName(), "유형 정보 없음"), i.getAmount(), i.getDescription()),
                                Collectors.toList())));
        return new ChargesResponse(month, balance(officeId), rows.stream().map(c -> new ChargeResponse(
                c.getId(), c.getYearMonth(), c.getTotalAmount(), c.getMileageDiscountAmount(),
                c.getFinalAmount(), c.getStatusCode(), name(c.getStatusName(), "상태 정보 없음"),
                details.getOrDefault(c.getId(), List.of()))).toList());
    }

    // by팀장: OFFICE → 청구 순으로 잠그고 잔액 확인·사용 이력·누적 할인을 한 트랜잭션으로 처리한다.
    @Transactional
    public ChargesResponse useMileage(Long officeId, Long chargeId, MileageUseRequest request) {
        if (request == null || request.amount() == null || request.amount() < 1000
                || request.amount() % 1000 != 0 || request.expectedDiscountAmount() == null
                || request.expectedDiscountAmount().signum() < 0) {
            throw failure(HttpStatus.BAD_REQUEST, "마일리지는 1,000P 이상, 1,000P 단위로 사용할 수 있습니다.");
        }
        Office office = offices.lockOffice(officeId)
                .orElseThrow(() -> failure(HttpStatus.UNAUTHORIZED, "로그인 정보를 확인해 주세요."));
        if (!"ACTIVE".equals(office.getStatus_code()) || office.getWithdrawn_at() != null) {
            throw failure(HttpStatus.FORBIDDEN, "사용 가능한 계정이 아닙니다.");
        }
        // 사용 직전 발생한 패널티도 같은 OFFICE 잠금·트랜잭션 안에서 청구에 반영한다.
        penalties.synchronize(officeId);
        OfficeCharge charge = charges.lockOwned(chargeId, officeId)
                .orElseThrow(() -> failure(HttpStatus.NOT_FOUND, "관리비 청구 내역을 찾을 수 없습니다."));
        if (!currentMonth().equals(charge.getYearMonth()) || !"BILLED".equals(charge.getStatusCode())) {
            throw failure(HttpStatus.CONFLICT, "이번 달 청구 완료 상태의 관리비에만 사용할 수 있습니다.");
        }
        if (charge.getTotalAmount() == null || charge.getMileageDiscountAmount() == null
                || charge.getFinalAmount() == null || charge.getMileageDiscountAmount().signum() < 0
                || charge.getFinalAmount().signum() < 0
                || charge.getTotalAmount().subtract(charge.getMileageDiscountAmount())
                        .compareTo(charge.getFinalAmount()) != 0) {
            throw failure(HttpStatus.CONFLICT, "청구 금액을 확인할 수 없습니다. 관리자에게 문의해 주세요.");
        }
        // by팀장: 동일 요청 재전송·다른 탭의 중복 차감을 누적 할인액으로 감지한다.
        if (charge.getMileageDiscountAmount().compareTo(request.expectedDiscountAmount()) != 0) {
            throw failure(HttpStatus.CONFLICT, "관리비가 변경되었습니다. 새로 조회한 뒤 다시 확인해 주세요.");
        }
        BigDecimal amount = BigDecimal.valueOf(request.amount());
        if (amount.compareTo(charge.getFinalAmount()) > 0) {
            throw failure(HttpStatus.CONFLICT, "최종 관리비를 초과해서 사용할 수 없습니다.");
        }
        if (amount.compareTo(balance(officeId)) > 0) {
            throw failure(HttpStatus.CONFLICT, "사용 가능한 마일리지가 부족합니다.");
        }
        MileagehistoryDto history = new MileagehistoryDto();
        history.setOffice(office);
        history.setMileagetypecode("USE");
        history.setAmount(-request.amount());
        history.setReferencetypecode("OFFICE_CHARGE");
        history.setReferenceid(charge.getId());
        history.setDescription(charge.getYearMonth() + " 관리비 마일리지 사용");
        history.setCreatedat(new Date());
        charge.applyMileage(amount);
        // 전체 영속성 컨텍스트를 flush하므로 청구 갱신 실패도 이력과 함께 롤백된다.
        mileage.saveAndFlush(history);
        return currentCharges(officeId);
    }

    // 본인 사무실의 주차 이용 내역을 표시명과 함께 페이지 단위로 반환한다.
    public Page<ParkingUsageResponse> parkingUsages(Long officeId, int page, int size) {
        return usages.findOwned(officeId, paging(page, size)).map(u -> new ParkingUsageResponse(
                u.getId(), u.getVehicleNumber(), u.getEntryAt(), u.getExitAt(),
                // 공통코드 표시명이 비어 있으면 화면에 사용할 대체 문구를 반환한다.
                name(u.getParkingTypeName(), "유형 정보 없음")));
    }

    // 본인 차량을 대상으로 승인된 신고 내역만 페이지 단위로 반환한다.
    public Page<AcceptedReportResponse> acceptedReports(Long officeId, int page, int size) {
        return reports.findOwned(officeId, paging(page, size)).map(r -> new AcceptedReportResponse(
                r.getId(), r.getVehicleNumber(), name(r.getTypeName(), "유형 정보 없음"),
                // 공통코드 표시명이 비어 있으면 화면에 사용할 대체 문구를 반환한다.
                name(r.getStatusName(), "상태 정보 없음"), r.getReviewReason(), r.getCreatedAt(), r.getReviewedAt()));
    }

    // 마일리지 적립·사용 이력을 합산하고 조회값이 없으면 0을 반환한다.
    private BigDecimal balance(Long officeId) {
        BigDecimal value = mileage.balance(officeId);
        return value == null ? BigDecimal.ZERO : value;
    }

    // 페이지 번호와 조회 건수 범위를 검사해 JPA 페이징 요청을 생성한다.
    private PageRequest paging(int page, int size) {
        if (page < 0 || size < 1 || size > 50) {
            throw failure(HttpStatus.BAD_REQUEST, "페이지는 0 이상, 조회 건수는 1~50이어야 합니다.");
        }
        return PageRequest.of(page, size);
    }

    // 한국 시간을 기준으로 현재 청구 연월을 yyyyMM 형식으로 반환한다.
    private String currentMonth() {
        return YearMonth.now(ZoneId.of("Asia/Seoul")).format(DateTimeFormatter.ofPattern("yyyyMM"));
    }

    // 공통코드 표시명이 비어 있으면 화면에 사용할 대체 문구를 반환한다.
    private String name(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    // 업무 오류 메시지와 HTTP 상태를 가진 예외를 생성한다.
    private ResponseStatusException failure(HttpStatus status, String message) {
        return new ResponseStatusException(status, message);
    }
}
