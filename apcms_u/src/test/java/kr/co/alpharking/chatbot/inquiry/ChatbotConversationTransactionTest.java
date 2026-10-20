package kr.co.alpharking.chatbot.inquiry;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;
import tools.jackson.databind.json.JsonMapper;

/** 실제 DB 없이 Spring 트랜잭션 경계가 실패 시 롤백을 요청하는지 확인합니다. */
class ChatbotConversationTransactionTest {
    static class TrackingTransactionManager extends AbstractPlatformTransactionManager {
        boolean committed;
        boolean rolledBack;
        @Override protected Object doGetTransaction() { return new Object(); }
        @Override protected void doBegin(Object tx, TransactionDefinition definition) {}
        @Override protected void doCommit(DefaultTransactionStatus status) { committed = true; }
        @Override protected void doRollback(DefaultTransactionStatus status) { rolledBack = true; }
    }

    @Test
    void answerInsertFailureRollsBackWholeExchange() {
        var repository = mock(ChatbotConversationRepository.class);
        when(repository.findExchange(anyLong(), anyString())).thenReturn(Optional.empty());
        when(repository.create(anyLong(), anyString())).thenReturn(101L);
        when(repository.insertMessage(eq(101L), eq("USER"), anyString(), anyString())).thenReturn("21");
        when(repository.insertMessage(eq(101L), eq("AI"), anyString(), anyString()))
                .thenThrow(new IllegalStateException("test insert failure"));
        var target = new ChatbotConversationService(repository, JsonMapper.builder().build());
        var manager = new TrackingTransactionManager();
        var interceptor = new TransactionInterceptor();
        interceptor.setTransactionManager(manager);
        interceptor.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
        var factory = new ProxyFactory(target);
        factory.addAdvice(interceptor);
        var service = (ChatbotConversationService) factory.getProxy();
        var request = new ChatbotConversationService.SaveRequest(null,
                "ff4f5590-2259-4b54-aaab-ff81b56a3d88", "질문", "답변", "POLICY", null);
        assertThrows(IllegalStateException.class, () -> service.save(2L, request));
        assertTrue(manager.rolledBack);
        assertFalse(manager.committed);
    }
}
