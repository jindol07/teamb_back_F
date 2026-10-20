package kr.co.alpharking.chatbot.inquiry;

import static org.junit.jupiter.api.Assertions.*;
import java.util.List;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.json.JsonMapper;

/** 실제 공통 SNAKE_CASE 설정에서도 챗봇 API의 JSON 계약이 유지되어야 합니다. */
class ChatbotJsonContractTest {
    private final JsonMapper mapper = JsonMapper.builder()
            .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE).build();

    @Test
    void profileUsesOfficeIdEvenWhenGlobalNamingIsSnakeCase() {
        var json = mapper.readTree(mapper.writeValueAsString(new ChatbotQueryController.Profile(11L)));
        assertEquals(11L, json.path("officeId").asLong());
        assertFalse(json.has("office_id"));
    }

    @Test
    void saveRequestAcceptsCamelCaseWithoutLosingConversationAndRequestIds() {
        var request = mapper.readValue("""
            {"conversationId":"101","requestId":"ff4f5590-2259-4b54-aaab-ff81b56a3d88",
             "question":"질문","answer":"답변","type":"POLICY","sources":[]}
            """, ChatbotConversationService.SaveRequest.class);
        assertEquals("101", request.conversationId());
        assertEquals("ff4f5590-2259-4b54-aaab-ff81b56a3d88", request.requestId());
    }

    @Test
    void savedAndRestoredMessagesUseTheSameContractAsFrontendAndFastApi() {
        var saved = new ChatbotConversationService.Saved("101", "21", "22", "답변", "POLICY",
                mapper.createArrayNode(), true);
        var json = mapper.readTree(mapper.writeValueAsString(saved));
        assertEquals("101", json.path("conversationId").asText());
        assertEquals("22", json.path("answerMessageId").asText());
        var history = new ChatbotConversationService.History("101", List.of(
                new ChatbotConversationRepository.Message("21", "USER", "질문")));
        var restored = mapper.readTree(mapper.writeValueAsString(history));
        assertEquals("101", restored.path("conversationId").asText());
        assertEquals("USER", restored.path("messages").get(0).path("senderTypeCode").asText());
    }
}
