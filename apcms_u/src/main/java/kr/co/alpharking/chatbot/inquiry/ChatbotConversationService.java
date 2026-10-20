package kr.co.alpharking.chatbot.inquiry;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

@Service
public class ChatbotConversationService {
    private final ChatbotConversationRepository repository;
    private final ObjectMapper mapper;
    public ChatbotConversationService(ChatbotConversationRepository repository, ObjectMapper mapper) {
        this.repository = repository;
        this.mapper = mapper;
    }

    @JsonNaming(PropertyNamingStrategies.LowerCamelCaseStrategy.class)
    public record SaveRequest(String conversationId, @NotBlank String requestId,
            @NotBlank @Size(max = 2000) String question,
            @NotBlank @Size(max = 16000) String answer, @NotBlank @Size(max = 50) String type,
            JsonNode sources) {}
    // NUMBER(19)는 JavaScript 정밀도 손실을 피하기 위해 JSON에서 문자열로 반환합니다.
    @JsonNaming(PropertyNamingStrategies.LowerCamelCaseStrategy.class)
    public record Saved(String conversationId, String questionMessageId, String answerMessageId,
                        String answer, String type, JsonNode sources, boolean saved) {}
    @JsonNaming(PropertyNamingStrategies.LowerCamelCaseStrategy.class)
    public record History(String conversationId, List<ChatbotConversationRepository.Message> messages) {}

    @Transactional
    public Saved save(long officeId, SaveRequest request) {
        String requestId;
        try {
            requestId = UUID.fromString(request.requestId()).toString();
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 ID는 UUID여야 합니다.");
        }
        Long conversationId = request.conversationId() == null ? null : parseId(request.conversationId());
        if (request.sources() != null && !request.sources().isArray()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "근거 정보는 배열이어야 합니다.");
        }
        repository.lockOffice(officeId);
        if (conversationId != null) requireOwner(conversationId, officeId);
        var previous = repository.findExchange(officeId, requestId);
        if (previous.isPresent()) {
            var exchange = previous.get();
            if (!exchange.question().equals(request.question())
                    || (conversationId != null && conversationId.longValue() != exchange.conversationId())) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 사용한 요청 ID입니다.");
            }
            requireOwner(exchange.conversationId(), officeId);
            var metadata = mapper.readTree(exchange.metadata());
            return new Saved(Long.toString(exchange.conversationId()), exchange.questionMessageId(),
                    exchange.answerMessageId(), exchange.answer(), metadata.path("type").asText(),
                    metadata.path("sources"), true);
        }
        JsonNode sources = request.sources() == null ? mapper.createArrayNode() : request.sources();
        String metadata = mapper.writeValueAsString(Map.of("requestId", requestId,
                "type", request.type(), "sources", sources));
        if (metadata.length() > 100000) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "근거 정보가 너무 큽니다.");
        }
        long id = conversationId == null ? repository.create(officeId, title(request.question())) : conversationId;
        String questionId = repository.insertMessage(id, "USER", request.question(), metadata);
        String answerId = repository.insertMessage(id, "AI", request.answer(), metadata);
        return new Saved(Long.toString(id), questionId, answerId, request.answer(), request.type(), sources, true);
    }

    @Transactional(readOnly = true)
    public History history(long officeId, String conversationId) {
        long id = parseId(conversationId);
        requireOwner(id, officeId);
        return new History(Long.toString(id), repository.messages(id));
    }

    @Transactional(readOnly = true)
    public History latest(long officeId) {
        return repository.latest(officeId).map(id -> history(officeId, id.toString()))
                .orElseGet(() -> new History(null, List.of()));
    }

    private void requireOwner(long id, long officeId) {
        if (!repository.ownsActive(id, officeId)) {
            // 타인의 대화 존재 여부를 구분해서 노출하지 않습니다.
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "조회 가능한 대화가 없습니다.");
        }
    }

    private long parseId(String value) {
        try {
            if (!value.matches("[1-9][0-9]{0,18}")) throw new NumberFormatException();
            return Long.parseLong(value);
        } catch (NumberFormatException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "대화 ID가 올바르지 않습니다.");
        }
    }

    static String title(String question) {
        String text = question.strip();
        StringBuilder result = new StringBuilder();
        for (int codePoint : text.codePoints().toArray()) {
            String next = result.toString() + new String(Character.toChars(codePoint));
            if (next.getBytes(StandardCharsets.UTF_8).length > 100) break;
            result.appendCodePoint(codePoint);
        }
        return result.toString();
    }
}
