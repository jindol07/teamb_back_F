package kr.co.alpharking.chatbot.reservation.test;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.security.Office;

class ChatbotReservationControllerTest {
    private final ChatbotReservationService service = mock(ChatbotReservationService.class);
    private final ChatbotReservationController controller = new ChatbotReservationController();

    @BeforeEach
    void setUp() { ReflectionTestUtils.setField(controller, "chatbotReservationService", service); }

    private Authentication office(long id) {
        Office office = new Office();
        office.setOffice_id(id);
        return new UsernamePasswordAuthenticationToken(office, null, office.getAuthorities());
    }

    @Test
    void ownReservationsUseAuthenticatedOffice() throws Exception {
        when(service.getReservations(15L)).thenReturn(List.of());
        MockMvcBuilders.standaloneSetup(controller).build()
                .perform(get("/api/chatbot/reservations").principal(office(15)).param("officeId", "99"))
                .andExpect(status().isOk());
        verify(service).getReservations(15L);
    }

    @Test
    void oldOfficeIdPathIsNoLongerAvailable() throws Exception {
        MockMvcBuilders.standaloneSetup(controller).build()
                .perform(get("/api/chatbot/reservations/99").principal(office(15)))
                .andExpect(status().isNotFound());
        verifyNoInteractions(service);
    }

    @Test
    void missingOrUnauthenticatedLoginIsRejected() {
        assertEquals(HttpStatus.UNAUTHORIZED, assertThrows(ResponseStatusException.class,
                () -> controller.getMyReservations(null)).getStatusCode());
        var unauthenticated = new UsernamePasswordAuthenticationToken("user", null);
        assertEquals(HttpStatus.UNAUTHORIZED, assertThrows(ResponseStatusException.class,
                () -> controller.getMyReservations(unauthenticated)).getStatusCode());
        verifyNoInteractions(service);
    }

    @Test
    void invalidPrincipalMissingIdOrWrongRoleIsRejected() {
        Office noId = new Office();
        Office office = new Office();
        office.setOffice_id(15L);
        var role = new SimpleGrantedAuthority("OFFICE");
        for (var auth : List.of(
                new UsernamePasswordAuthenticationToken("user", null, List.of(role)),
                new UsernamePasswordAuthenticationToken(noId, null, List.of(role)),
                new UsernamePasswordAuthenticationToken(office, null, List.of(new SimpleGrantedAuthority("ADMIN"))))) {
            assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                    () -> controller.getMyReservations(auth)).getStatusCode());
        }
        verifyNoInteractions(service);
    }
}
