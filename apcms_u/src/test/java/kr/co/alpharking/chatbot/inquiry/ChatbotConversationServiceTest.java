package kr.co.alpharking.chatbot.inquiry;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.json.JsonMapper;

class ChatbotConversationServiceTest {
    private final ChatbotConversationRepository repository = mock(ChatbotConversationRepository.class);
    private final JsonMapper mapper = JsonMapper.builder().build();
    private ChatbotConversationService service;
    private static final String REQUEST = "ff4f5590-2259-4b54-aaab-ff81b56a3d88";

    @BeforeEach
    void setUp() {
        service = new ChatbotConversationService(repository, mapper);
        when(repository.findExchange(anyLong(), anyString())).thenReturn(Optional.empty());
    }

    private ChatbotConversationService.SaveRequest request(String id) {
        return new ChatbotConversationService.SaveRequest(id, REQUEST, "내 주차이력 알려줘", "조회 결과",
                "USAGE", mapper.createArrayNode());
    }

    @Test
    void firstQuestionCreatesConversationAndUserAiPair() {
        when(repository.create(eq(2L), anyString())).thenReturn(9007199254740993L);
        when(repository.insertMessage(anyLong(), eq("USER"), anyString(), anyString())).thenReturn("21");
        when(repository.insertMessage(anyLong(), eq("AI"), anyString(), anyString())).thenReturn("22");
        var result = service.save(2L, request(null));
        assertEquals("9007199254740993", result.conversationId());
        assertTrue(result.saved());
        var order = inOrder(repository);
        order.verify(repository).lockOffice(2L);
        order.verify(repository).findExchange(2L, REQUEST);
        order.verify(repository).create(2L, "내 주차이력 알려줘");
        order.verify(repository).insertMessage(eq(9007199254740993L), eq("USER"), anyString(), contains(REQUEST));
        order.verify(repository).insertMessage(eq(9007199254740993L), eq("AI"), anyString(), contains(REQUEST));
    }

    @Test
    void existingConversationRequiresOwnerAndDoesNotCreateAgain() {
        when(repository.ownsActive(101L, 2L)).thenReturn(true);
        service.save(2L, request("101"));
        verify(repository, never()).create(anyLong(), anyString());
        verify(repository).insertMessage(eq(101L), eq("USER"), anyString(), anyString());
    }

    @Test
    void anotherOfficeCannotReadOrAppendMessages() {
        assertEquals(HttpStatus.NOT_FOUND, assertThrows(ResponseStatusException.class,
                () -> service.history(3L, "101")).getStatusCode());
        assertThrows(ResponseStatusException.class, () -> service.save(3L, request("101")));
        verify(repository, never()).messages(anyLong());
        verify(repository, never()).insertMessage(anyLong(), anyString(), anyString(), anyString());
    }

    @Test
    void sameRequestReturnsOriginalAnswerWithoutDuplicateInsert() {
        when(repository.ownsActive(101L, 2L)).thenReturn(true);
        when(repository.findExchange(2L, REQUEST)).thenReturn(Optional.of(
            new ChatbotConversationRepository.Exchange(101L, "내 주차이력 알려줘", "원래 저장된 답변",
                "{\"type\":\"USAGE\",\"sources\":[]}", "21", "22")));
        var result = service.save(2L, request(null));
        assertEquals("101", result.conversationId());
        assertEquals("원래 저장된 답변", result.answer());
        verify(repository, never()).create(anyLong(), anyString());
        verify(repository, never()).insertMessage(anyLong(), anyString(), anyString(), anyString());
    }

    @Test
    void requestIdCannotBeReusedForDifferentQuestion() {
        when(repository.findExchange(2L, REQUEST)).thenReturn(Optional.of(
            new ChatbotConversationRepository.Exchange(101L, "다른 질문", "답변", "{}", "21", "22")));
        assertEquals(HttpStatus.CONFLICT, assertThrows(ResponseStatusException.class,
                () -> service.save(2L, request(null))).getStatusCode());
    }

    @Test
    void latestHistoryIsScopedToCurrentOffice() {
        when(repository.latest(3L)).thenReturn(Optional.of(102L));
        when(repository.ownsActive(102L, 3L)).thenReturn(true);
        when(repository.messages(102L)).thenReturn(List.of());
        assertEquals("102", service.latest(3L).conversationId());
        verify(repository).ownsActive(102L, 3L);
    }

    @Test
    void invalidIdsFailBeforeDatabaseAccess() {
        assertThrows(ResponseStatusException.class, () -> service.save(2L, request("uuid-not-number")));
        assertThrows(ResponseStatusException.class, () -> service.history(2L, "9223372036854775808"));
        verifyNoInteractions(repository);
    }

    @Test
    void unicodeTitleFitsHundredBytesWithoutBrokenCharacters() {
        var title = ChatbotConversationService.title("한글😀".repeat(50));
        assertTrue(title.getBytes(StandardCharsets.UTF_8).length <= 100);
        assertFalse(title.endsWith("\uD83D"));
        assertFalse(title.isBlank());
    }
}
