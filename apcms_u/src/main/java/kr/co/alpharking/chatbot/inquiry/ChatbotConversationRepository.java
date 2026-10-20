package kr.co.alpharking.chatbot.inquiry;

import java.util.List;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

@Repository
public class ChatbotConversationRepository {
    private final JdbcTemplate jdbc;
    public ChatbotConversationRepository(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @JsonNaming(PropertyNamingStrategies.LowerCamelCaseStrategy.class)
    public record Message(String id, String senderTypeCode, String content) {}
    public record Exchange(long conversationId, String question, String answer,
                           String metadata, String questionMessageId, String answerMessageId) {}

    // 동일 Office의 첫 질문/재시도를 직렬화하여 스키마 변경 없이 중복 INSERT를 방지합니다.
    public void lockOffice(long officeId) {
        jdbc.queryForObject("SELECT OFFICE_ID FROM OFFICE WHERE OFFICE_ID = ? FOR UPDATE", Long.class, officeId);
    }

    public boolean ownsActive(long id, long officeId) {
        return jdbc.queryForObject("""
            SELECT COUNT(*) FROM INQUIRY_CONVERSATION
            WHERE INQUIRY_CONVERSATION_ID = ? AND OFFICE_ID = ? AND ENDED_AT IS NULL
            """, Integer.class, id, officeId) == 1;
    }

    public Optional<Long> latest(long officeId) {
        return jdbc.query("""
            SELECT INQUIRY_CONVERSATION_ID FROM INQUIRY_CONVERSATION
            WHERE OFFICE_ID = ? AND ENDED_AT IS NULL
            ORDER BY CREATED_AT DESC, INQUIRY_CONVERSATION_ID DESC FETCH FIRST 1 ROW ONLY
            """, (rs, row) -> rs.getLong(1), officeId).stream().findFirst();
    }

    public Optional<Exchange> findExchange(long officeId, String requestId) {
        return jdbc.query("""
            SELECT c.INQUIRY_CONVERSATION_ID, q.MESSAGE_CONTENT AS QUESTION,
                   a.MESSAGE_CONTENT AS ANSWER, a.RAG_SOURCE_JSON AS METADATA,
                   q.INQUIRY_MESSAGE_ID AS QUESTION_ID, a.INQUIRY_MESSAGE_ID AS ANSWER_ID
            FROM INQUIRY_CONVERSATION c
            JOIN INQUIRY_MESSAGE q ON q.INQUIRY_CONVERSATION_ID = c.INQUIRY_CONVERSATION_ID
            JOIN INQUIRY_MESSAGE a ON a.INQUIRY_CONVERSATION_ID = c.INQUIRY_CONVERSATION_ID
            WHERE c.OFFICE_ID = ? AND q.SENDER_TYPE_CODE = 'USER' AND a.SENDER_TYPE_CODE = 'AI'
              AND JSON_VALUE(q.RAG_SOURCE_JSON, '$.requestId' RETURNING VARCHAR2(36) NULL ON ERROR) = ?
              AND JSON_VALUE(a.RAG_SOURCE_JSON, '$.requestId' RETURNING VARCHAR2(36) NULL ON ERROR) = ?
            """, (rs, row) -> new Exchange(rs.getLong("INQUIRY_CONVERSATION_ID"),
                rs.getString("QUESTION"), rs.getString("ANSWER"), rs.getString("METADATA"),
                rs.getString("QUESTION_ID"), rs.getString("ANSWER_ID")), officeId, requestId, requestId)
            .stream().findFirst();
    }

    public long create(long officeId, String title) {
        long id = jdbc.queryForObject("SELECT SEQ_INQUIRY_CONVERSATION.NEXTVAL FROM DUAL", Long.class);
        jdbc.update("""
            INSERT INTO INQUIRY_CONVERSATION (INQUIRY_CONVERSATION_ID, OFFICE_ID, TITLE, CREATED_AT)
            VALUES (?, ?, ?, SYSDATE)
            """, id, officeId, title);
        return id;
    }

    public String insertMessage(long conversationId, String sender, String content, String metadata) {
        long id = jdbc.queryForObject("SELECT SEQ_INQUIRY_MESSAGE.NEXTVAL FROM DUAL", Long.class);
        // CLOB은 문자 스트림으로 전달하여 긴 답변도 VARCHAR 바인딩 제한을 받지 않습니다.
        jdbc.update("""
            INSERT INTO INQUIRY_MESSAGE (INQUIRY_MESSAGE_ID, INQUIRY_CONVERSATION_ID,
                SENDER_TYPE_CODE, MESSAGE_CONTENT, RAG_SOURCE_JSON, CREATED_AT)
            VALUES (?, ?, ?, ?, ?, SYSDATE)
            """, ps -> {
                ps.setLong(1, id);
                ps.setLong(2, conversationId);
                ps.setString(3, sender);
                ps.setCharacterStream(4, new java.io.StringReader(content), content.length());
                ps.setCharacterStream(5, new java.io.StringReader(metadata), metadata.length());
            });
        return Long.toString(id);
    }

    public List<Message> messages(long conversationId) {
        return jdbc.query("""
            SELECT * FROM (
                SELECT INQUIRY_MESSAGE_ID, SENDER_TYPE_CODE, MESSAGE_CONTENT FROM INQUIRY_MESSAGE
                WHERE INQUIRY_CONVERSATION_ID = ? AND SENDER_TYPE_CODE IN ('USER', 'AI')
                ORDER BY INQUIRY_MESSAGE_ID DESC FETCH FIRST 40 ROWS ONLY
            ) ORDER BY INQUIRY_MESSAGE_ID ASC
            """, (rs, row) -> new Message(rs.getString("INQUIRY_MESSAGE_ID"),
                rs.getString("SENDER_TYPE_CODE"), rs.getString("MESSAGE_CONTENT")), conversationId);
    }
}
