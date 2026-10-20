package kr.co.alpharking.chatbot.inquiry;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.web.authentication.WebAuthenticationDetails;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import kr.co.alpharking.security.Office;

class ChatbotQueryControllerTest {
    private final ChatbotQueryService service = mock(ChatbotQueryService.class);
    private final ChatbotQueryController controller = new ChatbotQueryController(service);

    private Authentication login(long id) {
        Office office = new Office();
        office.setOffice_id(id);
        var authentication = new UsernamePasswordAuthenticationToken(office, null, office.getAuthorities());
        // 실제 JWT 필터처럼 details에 요청 정보가 있어도 Office ID를 올바르게 추출해야 합니다.
        authentication.setDetails(mock(WebAuthenticationDetails.class));
        return authentication;
    }

    @Test
    void identityComesFromAuthenticatedOffice() {
        assertEquals(2L, controller.me(login(2)).officeId());
        assertEquals(3L, controller.me(login(3)).officeId());
        verifyNoInteractions(service);
    }

    @Test
    void everyQueryPassesOnlyCurrentOfficeId() {
        controller.usage(login(2));
        controller.reservations(login(3));
        controller.vehicles(login(4));
        verify(service).usage(2L);
        verify(service).reservations(3L);
        verify(service).vehicles(4L);
        verifyNoMoreInteractions(service);
    }

    @Test
    void missingAuthenticationNeverQueriesData() {
        assertEquals(HttpStatus.UNAUTHORIZED, assertThrows(ResponseStatusException.class,
                () -> controller.usage(null)).getStatusCode());
        verifyNoInteractions(service);
    }

    @Test
    void adminAndAnonymousCannotQueryOfficeData() {
        Authentication admin = new UsernamePasswordAuthenticationToken("admin", null,
                List.of(new SimpleGrantedAuthority("ADMIN")));
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                () -> controller.vehicles(admin)).getStatusCode());
        Authentication anonymous = new UsernamePasswordAuthenticationToken("anonymousUser", null,
                List.of(new SimpleGrantedAuthority("ROLE_ANONYMOUS")));
        assertThrows(ResponseStatusException.class, () -> controller.reservations(anonymous));
        verifyNoInteractions(service);
    }

    @Test
    void clientSuppliedOfficeIdCannotOverrideAuthenticatedOwner() throws Exception {
        var mvc = MockMvcBuilders.standaloneSetup(controller).build();
        mvc.perform(get("/api/chatbot/me/usage").principal(login(2)).param("officeId", "999"))
                .andExpect(status().isOk());
        verify(service).usage(2L);
        verifyNoMoreInteractions(service);
    }
}
