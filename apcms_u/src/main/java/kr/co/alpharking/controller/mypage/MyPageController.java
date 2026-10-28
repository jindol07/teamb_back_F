package kr.co.alpharking.controller.mypage;

import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.mypage.MyPageDtos.*;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.service.mypage.MyPageService;
import kr.co.alpharking.service.mypage.MyPageAccountService;
import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/mypage")
@RequiredArgsConstructor
public class MyPageController {
    private final MyPageService service;
    private final MyPageAccountService accounts;

    @PostMapping("/charges/current/penalties")
    // 사용자 화면 진입 시 미반영 패널티를 당월 관리비에 합산하고 최신 청구를 응답한다.
    public ChargesResponse synchronizePenalties(@AuthenticationPrincipal Object principal) {
        return service.synchronizePenalties(officeId(principal));
    }

    @GetMapping("/penalties")
    // 본인 소속 차량의 실제 패널티와 위반 금액을 페이지 응답으로 제공한다.
    public Page<PenaltyResponse> penalties(@AuthenticationPrincipal Object principal,
            @RequestParam(name = "page", defaultValue = "0") int page,
            @RequestParam(name = "size", defaultValue = "10") int size) {
        return service.penalties(officeId(principal), page, size);
    }

    @PatchMapping("/password")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    // 인증된 사용자의 비밀번호 변경 요청을 계정 서비스에 전달한다.
    public void changePassword(@AuthenticationPrincipal Object principal,
            @Valid @RequestBody PasswordChangeRequest request) {
        accounts.changePassword(officeId(principal), request);
    }

    @PostMapping("/withdrawal")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    // 인증된 사용자의 회원 탈퇴 요청을 계정 서비스에 전달한다.
    public void withdraw(@AuthenticationPrincipal Object principal,
            @Valid @RequestBody WithdrawRequest request) {
        accounts.withdraw(officeId(principal), request);
    }

    @GetMapping("/charges/current")
    // 인증된 사용자의 당월 관리비 조회 결과를 응답한다.
    public ChargesResponse currentCharges(@AuthenticationPrincipal Object principal) {
        return service.currentCharges(officeId(principal));
    }

    @PostMapping("/charges/{chargeId}/mileage")
    // 인증된 사용자의 관리비 마일리지 사용 요청을 처리하고 최신 청구를 응답한다.
    public ChargesResponse useMileage(@AuthenticationPrincipal Object principal,
            @PathVariable("chargeId") Long chargeId, @Valid @RequestBody MileageUseRequest request) {
        return service.useMileage(officeId(principal), chargeId, request);
    }

    @GetMapping("/parking-usages")
    // 인증된 사용자의 주차 이용 내역을 페이지 응답으로 제공한다.
    public Page<ParkingUsageResponse> parkingUsages(@AuthenticationPrincipal Object principal,
            @RequestParam(name = "page", defaultValue = "0") int page,
            @RequestParam(name = "size", defaultValue = "10") int size) {
        return service.parkingUsages(officeId(principal), page, size);
    }

    @GetMapping("/accepted-reports")
    // 인증된 사용자의 승인 신고 내역을 페이지 응답으로 제공한다.
    public Page<AcceptedReportResponse> acceptedReports(@AuthenticationPrincipal Object principal,
            @RequestParam(name = "page", defaultValue = "0") int page,
            @RequestParam(name = "size", defaultValue = "10") int size) {
        return service.acceptedReports(officeId(principal), page, size);
    }

    // 인증 principal의 사용자 유형과 활성 상태를 확인하고 사무실 식별자를 추출한다.
    private Long officeId(Object principal) {
        if (principal == null) throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다.");
        if (!(principal instanceof Office office) || office.getOffice_id() == null
                || !"ACTIVE".equals(office.getStatus_code()) || office.getWithdrawn_at() != null) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "사용 가능한 사용자 계정이 아닙니다.");
        }
        return office.getOffice_id();
    }
}
