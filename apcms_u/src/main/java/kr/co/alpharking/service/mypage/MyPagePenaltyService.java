package kr.co.alpharking.service.mypage;

import java.time.YearMonth;
import java.time.ZoneId;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.math.BigDecimal;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.mypage.MyPageDtos.PenaltyResponse;
import kr.co.alpharking.entity.mypage.OfficeCharge;
import kr.co.alpharking.entity.mypage.OfficeChargeItem;
import kr.co.alpharking.repository.mypage.*;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class MyPagePenaltyService {
    private final MyPageOfficeRepository offices;
    private final OfficeChargeRepository charges;
    private final OfficeChargeItemRepository items;
    private final MyPagePenaltyRepository penalties;

    // 실제 패널티의 위반 금액·공통코드 유형명·부과 사유를 본인 기준으로 조회한다.
    @Transactional(readOnly = true)
    public Page<PenaltyResponse> findOwned(Long officeId, int page, int size) {
        if (page < 0 || size < 1 || size > 50) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "페이지는 0 이상, 조회 건수는 1~50이어야 합니다.");
        }
        return penalties.findOwned(officeId, PageRequest.of(page, size)).map(p -> new PenaltyResponse(
                p.getId(), p.getVehicleNumber(), p.getTypeName() == null ? "유형 정보 없음" : p.getTypeName(),
                p.getPenaltyAmount(), p.getReason(), p.getImposedAt()));
    }

    // by팀장: 본인 당월 미반영 패널티를 한 번만 청구하고 필요하면 기존 시퀀스로 청구를 생성한다.
    @Transactional
    public void synchronize(Long officeId) {
        var office = offices.lockOffice(officeId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인 정보를 확인해 주세요."));
        if (!"ACTIVE".equals(office.getStatus_code()) || office.getWithdrawn_at() != null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "사용 가능한 계정이 아닙니다.");
        }
        YearMonth month = YearMonth.now(ZoneId.of("Asia/Seoul"));
        String yearMonth = month.format(DateTimeFormatter.ofPattern("yyyyMM"));
        List<OfficeCharge> current = charges.lockCurrent(officeId, yearMonth);
        var pending = penalties.lockUnbilled(officeId, month.atDay(1).atStartOfDay(), month.plusMonths(1).atDay(1).atStartOfDay());
        if (pending.isEmpty()) return;
        // 잠금 대기 중 다른 청구가 커밋된 경우에도 패널티를 다시 합산하지 않는다.
        pending = pending.stream().filter(p -> !items.existsByChargeTypeCodeAndReferenceId("PENALTY", p.getId())).toList();
        if (pending.isEmpty()) return;
        OfficeCharge target = current.stream().filter(c -> "BILLED".equals(c.getStatusCode())).findFirst()
                .orElseGet(() -> current.stream().filter(c -> "READY".equals(c.getStatusCode())).findFirst().orElse(null));
        LocalDateTime now = LocalDateTime.now(ZoneId.of("Asia/Seoul"));
        if (target == null) {
            target = charges.saveAndFlush(OfficeCharge.forPenalty(officeId, yearMonth, now));
        }
        if (target.getTotalAmount() == null || target.getMileageDiscountAmount() == null || target.getFinalAmount() == null
                || target.getMileageDiscountAmount().signum() < 0 || target.getFinalAmount().signum() < 0
                || target.getTotalAmount().subtract(target.getMileageDiscountAmount()).compareTo(target.getFinalAmount()) != 0) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "청구 금액이 일치하지 않아 패널티를 반영할 수 없습니다.");
        }
        BigDecimal added = pending.stream().map(p -> p.getAmount()).reduce(BigDecimal.ZERO, BigDecimal::add);
        if (target.getTotalAmount().add(added).compareTo(new BigDecimal("9999999999.99")) > 0) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "관리비 청구 금액 범위를 초과했습니다.");
        }
        var details = new java.util.ArrayList<OfficeChargeItem>();
        for (var penalty : pending) {
            target.addPenalty(penalty.getAmount());
            details.add(OfficeChargeItem.forPenalty(target.getId(), penalty, now));
        }
        // 상세의 PENALTY+REFERENCE_ID를 중복 확인 기준으로 쓰며 헤더와 상세 실패는 함께 롤백한다.
        items.saveAllAndFlush(details);
    }
}
