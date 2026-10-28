package kr.co.alpharking.service.mypage;

import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.mypage.MyPageDtos.PasswordChangeRequest;
import kr.co.alpharking.dto.mypage.MyPageDtos.WithdrawRequest;
import kr.co.alpharking.repository.mypage.MyPageOfficeRepository;
import kr.co.alpharking.repository.mypage.MyPageCompanyRepository;
import kr.co.alpharking.security.Office;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class MyPageAccountService {
    private final MyPageOfficeRepository offices;
    private final PasswordEncoder passwordEncoder;
    private final MyPageCompanyRepository companies;

    @Transactional
    // 현재 비밀번호를 검증한 뒤 새 비밀번호 해시와 수정일을 갱신한다.
    public void changePassword(Long officeId, PasswordChangeRequest request) {
        if (request == null || request.currentPassword() == null || request.currentPassword().isBlank()
                || request.newPassword() == null || request.newPassword().isBlank()
                || request.newPassword().length() < 8 || request.newPassword().length() > 20
                || !request.newPassword().equals(request.confirmPassword())) {
            throw failure(HttpStatus.BAD_REQUEST, "새 비밀번호는 8~20자로 입력하고 확인 값과 일치해야 합니다.");
        }
        Office office = activeOffice(officeId);
        if (office.getPassword() == null || !passwordEncoder.matches(request.currentPassword(), office.getPassword())) {
            throw failure(HttpStatus.BAD_REQUEST, "현재 비밀번호가 올바르지 않습니다.");
        }
        // by팀장: 회원가입에 사용하는 PasswordEncoder로 새 비밀번호를 해시하고 기존 엔티티를 갱신한다.
        office.setPassword(passwordEncoder.encode(request.newPassword()));
        offices.updateTimestamp(officeId);
        offices.flush();
    }

    @Transactional
    // 본인 확인·유니크 충돌 검사를 거쳐 회사와 사무실을 한 트랜잭션으로 탈퇴 처리한다.
    public void withdraw(Long officeId, WithdrawRequest request) {
        if (request == null || request.currentPassword() == null || request.currentPassword().isBlank()
                || !"탈퇴".equals(request.confirmation())) {
            throw failure(HttpStatus.BAD_REQUEST, "현재 비밀번호와 탈퇴 확인 문구를 입력해 주세요.");
        }
        Office office = activeOffice(officeId);
        if (office.getPassword() == null || !passwordEncoder.matches(request.currentPassword(), office.getPassword())) {
            throw failure(HttpStatus.BAD_REQUEST, "현재 비밀번호가 올바르지 않습니다.");
        }
        var company = companies.lockCompany(office.getCompany_id())
                .orElseThrow(() -> failure(HttpStatus.CONFLICT, "소속 회사 정보를 확인할 수 없습니다."));
        if (company.getDeleted_at() != null || offices.countOtherMembers(company.getCompany_id(), officeId) > 0) {
            throw failure(HttpStatus.CONFLICT, "같은 회사에 다른 회원이 있거나 회사 상태를 확인할 수 없습니다. 관리자에게 문의해 주세요.");
        }
        String day = offices.deletionDay();
        String username = deletedValue(office.getUsername(), 50, day);
        String email = deletedValue(office.getEmail(), 100, day);
        String phone = deletedValue(office.getPhone(), 50, day);
        String businessNumber = deletedValue(company.getBusiness_number(), 50, day);
        if (offices.countUniqueConflicts(officeId, username, email, phone) > 0
                || (businessNumber != null && companies.countBusinessConflicts(company.getCompany_id(), businessNumber) > 0)) {
            throw failure(HttpStatus.CONFLICT, "탈퇴 처리용 값이 이미 존재합니다. 관리자에게 문의해 주세요.");
        }
        try {
            // by팀장: 유니크 값을 해제하고 OFFICE·COMPANY를 SYSDATE로 함께 소프트 삭제한다.
            // 기존 로그인 코드 수정 없이 접미사 ID와 원래 비밀번호를 이용한 재로그인을 막는다.
            String disabledPassword = passwordEncoder.encode(UUID.randomUUID().toString());
            if (offices.withdraw(officeId, username, email, phone, disabledPassword) != 1
                    || companies.softDelete(company.getCompany_id(), businessNumber) != 1) {
                throw failure(HttpStatus.CONFLICT, "계정 상태가 변경되었습니다. 다시 확인해 주세요.");
            }
        } catch (DataIntegrityViolationException conflict) {
            throw failure(HttpStatus.CONFLICT, "탈퇴 처리 중 데이터 충돌이 발생했습니다. 관리자에게 문의해 주세요.");
        }
    }

    // by팀장: Oracle VARCHAR2의 BYTE 길이도 초과하지 않도록 코드 포인트 단위로 앞부분을 줄인다.
    static String deletedValue(String value, int maxBytes, String day) {
        if (value == null) return null;
        if (day == null || !day.matches("\\d{4}")) throw new IllegalStateException("DB 기준 날짜를 확인할 수 없습니다.");
        String suffix = "_d_" + day;
        int budget = maxBytes - suffix.length();
        var prefix = new StringBuilder();
        int bytes = 0;
        for (int offset = 0; offset < value.length();) {
            int codePoint = value.codePointAt(offset);
            String next = new String(Character.toChars(codePoint));
            int length = next.getBytes(StandardCharsets.UTF_8).length;
            if (bytes + length > budget) break;
            prefix.append(next); bytes += length; offset += Character.charCount(codePoint);
        }
        return prefix + suffix;
    }

    // 사무실 행을 잠그고 현재 서비스 이용이 가능한 계정인지 확인한다.
    private Office activeOffice(Long officeId) {
        Office office = offices.lockOffice(officeId)
                .orElseThrow(() -> failure(HttpStatus.UNAUTHORIZED, "로그인 정보를 확인해 주세요."));
        if (!"ACTIVE".equals(office.getStatus_code()) || office.getWithdrawn_at() != null) {
            throw failure(HttpStatus.FORBIDDEN, "사용 가능한 계정이 아닙니다.");
        }
        return office;
    }

    // 계정 처리 실패 사유를 지정한 HTTP 상태의 예외로 변환한다.
    private ResponseStatusException failure(HttpStatus status, String message) {
        return new ResponseStatusException(status, message);
    }
}
