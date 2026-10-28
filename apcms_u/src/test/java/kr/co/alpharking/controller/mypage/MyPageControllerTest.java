package kr.co.alpharking.controller.mypage;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.mypage.MyPageDtos.*;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.service.mypage.MyPageService;
import kr.co.alpharking.service.mypage.MyPageAccountService;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.json.JsonMapper;

class MyPageControllerTest {
    private final MyPageService service = mock(MyPageService.class);
    private final MyPageAccountService accounts = mock(MyPageAccountService.class);
    private final MyPageController controller = new MyPageController(service, accounts);

    @Test
    // 미인증·잘못된 유형·비활성 계정 요청이 서비스에 전달되지 않는지 검증한다.
    void missingWrongAndInactivePrincipalNeverReachService() {
        assertEquals(HttpStatus.UNAUTHORIZED, assertThrows(ResponseStatusException.class,
                () -> controller.currentCharges(null)).getStatusCode());
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                () -> controller.parkingUsages(new Object(), 0, 10)).getStatusCode());
        var office = new Office(); office.setOffice_id(12L); office.setStatus_code("WITHDRAWN");
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                () -> controller.acceptedReports(office, 0, 10)).getStatusCode());
        verifyNoInteractions(service, accounts);
    }

    @Test
    // 차감 요청의 사무실 ID가 인증 정보에서만 결정되는지 검증한다.
    void mutationUsesOnlyAuthenticatedOfficeIdentity() {
        var office = new Office(); office.setOffice_id(12L); office.setStatus_code("ACTIVE");
        var request = new MileageUseRequest(1000L, BigDecimal.ZERO);
        controller.useMileage(office, 33L, request);
        verify(service).useMileage(12L, 33L, request);
    }

    @Test
    // 관리비 요청·응답의 snake_case JSON이 프론트 계약과 일치하는지 검증한다.
    void snakeCaseRequestAndResponseMatchFrontendContract() {
        var mapper = JsonMapper.builder().propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE).build();
        var request = mapper.readValue("""
                {"amount":1000,"expected_discount_amount":2000}
                """, MileageUseRequest.class);
        assertEquals(1000L, request.amount());
        assertEquals(0, new BigDecimal("2000").compareTo(request.expectedDiscountAmount()));
        var response = new ChargesResponse("202610", BigDecimal.TEN, List.of(new ChargeResponse(
                33L, "202610", BigDecimal.TEN, BigDecimal.ZERO, BigDecimal.TEN, "BILLED", "청구완료", List.of())));
        var json = mapper.readTree(mapper.writeValueAsString(response));
        assertEquals("202610", json.path("year_month").asText());
        assertTrue(json.has("mileage_balance"));
        assertEquals("청구완료", json.path("charges").get(0).path("status_name").asText());
    }

    @Test
    // 페이징 메타데이터와 목록 항목이 동일한 snake_case 규칙을 따르는지 검증한다.
    void pageMetadataAndRowsUseTheSameSnakeCaseContract() {
        var mapper = JsonMapper.builder().propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE).build();
        var page = new PageImpl<>(List.of(new ParkingUsageResponse(1L, "예시", null, null, "방문")),
                PageRequest.of(1, 10), 25);
        var json = mapper.readTree(mapper.writeValueAsString(page));
        assertEquals(1, json.path("number").asInt());
        assertEquals(3, json.path("total_pages").asInt());
        assertEquals(25, json.path("total_elements").asInt());
        assertEquals("방문", json.path("content").get(0).path("parking_type_name").asText());
    }

    @Test
    // 비밀번호 변경·탈퇴가 인증된 본인에게만 전달되는지 검증한다.
    void accountMutationsUseAuthenticatedIdentityAndRejectAnonymousRequests() {
        var office = new Office(); office.setOffice_id(12L); office.setStatus_code("ACTIVE");
        var password = new PasswordChangeRequest("old-password", "new-password", "new-password");
        var withdrawal = new WithdrawRequest("old-password", "탈퇴");
        controller.changePassword(office, password);
        controller.withdraw(office, withdrawal);
        verify(accounts).changePassword(12L, password);
        verify(accounts).withdraw(12L, withdrawal);
        assertThrows(ResponseStatusException.class, () -> controller.changePassword(null, password));
        assertThrows(ResponseStatusException.class, () -> controller.withdraw(null, withdrawal));
        verifyNoMoreInteractions(accounts);
    }

    @Test
    // 비밀번호 변경과 탈퇴 DTO가 snake_case 입력을 올바르게 읽는지 검증한다.
    void accountRequestDtosRespectSnakeCaseNaming() {
        var mapper = JsonMapper.builder().propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE).build();
        var password = mapper.readValue("""
                {"current_password":"old-password","new_password":"new-password","confirm_password":"new-password"}
                """, PasswordChangeRequest.class);
        assertEquals("old-password", password.currentPassword());
        assertEquals(password.newPassword(), password.confirmPassword());
        var withdrawal = mapper.readValue("""
                {"current_password":"old-password","confirmation":"탈퇴"}
                """, WithdrawRequest.class);
        assertEquals("탈퇴", withdrawal.confirmation());
    }

    // 신규 패널티 조회와 청구 반영이 인증된 본인 사무실에만 전달되는지 검증한다.
    @Test
    void penaltyEndpointsUseAuthenticatedOfficeAndRejectAnonymousAccess() {
        var office = new Office(); office.setOffice_id(15L); office.setStatus_code("ACTIVE");
        controller.penalties(office, 0, 10); controller.synchronizePenalties(office);
        verify(service).penalties(15L, 0, 10);
        verify(service).synchronizePenalties(15L);
        assertThrows(ResponseStatusException.class, () -> controller.penalties(null, 0, 10));
        assertThrows(ResponseStatusException.class, () -> controller.synchronizePenalties(null));
        verifyNoMoreInteractions(service);
    }

    // 신규 위반 금액이 프론트에서 읽는 penalty_amount 이름으로 직렬화되는지 검증한다.
    @Test
    void penaltyAmountIsSerializedInSnakeCase() {
        var mapper = JsonMapper.builder().propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE).build();
        var response = new PenaltyResponse(55L, "예시 차량", "지정구역위반", new BigDecimal("10000"), "부과 사유", null);
        var json = mapper.readTree(mapper.writeValueAsString(response));
        assertEquals(10000, json.path("penalty_amount").asInt());
        assertEquals("지정구역위반", json.path("type_name").asText());
    }
}
