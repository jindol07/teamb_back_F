package kr.co.alpharking.chatbot.inquiry;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.security.Office;

class ChatbotConversationControllerTest {
    private final ChatbotConversationService service = mock(ChatbotConversationService.class);
    private final ChatbotConversationController controller = new ChatbotConversationController(service);

    @Test
    void noAuthenticationCannotReadOrWrite() {
        assertThrows(ResponseStatusException.class, () -> controller.latest(null));
        assertThrows(ResponseStatusException.class, () -> controller.messages(null, "101"));
        assertThrows(ResponseStatusException.class, () -> controller.save(null, null));
        verifyNoInteractions(service);
    }

    @Test
    void requestOfficeIdCannotOverrideAuthenticatedOffice() throws Exception {
        var office = new Office();
        office.setOffice_id(2L);
        var auth = new UsernamePasswordAuthenticationToken(office, null, office.getAuthorities());
        var mvc = MockMvcBuilders.standaloneSetup(controller).build();
        mvc.perform(get("/api/chatbot/conversations/101/messages").principal(auth).param("officeId", "999"))
                .andExpect(status().isOk());
        verify(service).history(2L, "101");
        verifyNoMoreInteractions(service);
    }
}
