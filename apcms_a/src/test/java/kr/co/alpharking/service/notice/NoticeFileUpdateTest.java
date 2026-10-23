package kr.co.alpharking.service.notice;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import kr.co.alpharking.dao.notice.NoticeDao;
import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.dto.notice.NoticeFiles;
import kr.co.alpharking.dto.notice.NoticeHistory;

class NoticeFileUpdateTest {
    private NoticeDao dao;
    private NoticeService service;
    private NoticeCreateReq notice;

    @BeforeEach
    void setUp() {
        dao = mock(NoticeDao.class);
        service = new NoticeService();
        ReflectionTestUtils.setField(service, "noticeDao", dao);
        notice = new NoticeCreateReq();
        notice.setNoticeId(10);
        notice.setWriterAdminId(1);
        notice.setTitle("notice");
        notice.setCreatedAt("2026-10-23 10:00:00");
        when(dao.findById(10)).thenReturn(notice);
        when(dao.getCurrentDateTime()).thenReturn("2026-10-23 11:00:00");
        when(dao.closeCurrentNoticeHistory(eq(10), anyString())).thenReturn(1);
        when(dao.updateNotice(same(notice), anyString())).thenReturn(1);
    }

    @Test
    void noNewFileLeavesAttachmentUntouched() {
        assertTrue(service.updateNoticeWithFile(notice, null, 7L));
        verify(dao, never()).findFilesByNoticeId(anyInt());
        verify(dao, never()).updateNoticeFile(any());
        verify(dao, never()).addfile(anyList());
    }

    @Test
    void replacementKeepsAttachmentIdAndRecordsOldFile() {
        NoticeFiles old = new NoticeFiles();
        old.setNoticeAttachmentId(30);
        old.setOriginalName("old.txt");
        old.setFilePath("old-path");
        when(dao.findFilesByNoticeId(10)).thenReturn(List.of(old));
        when(dao.updateNoticeFile(any())).thenReturn(1);
        NoticeFiles file = new NoticeFiles();
        file.setOriginalName("new.txt");
        assertTrue(service.updateNoticeWithFile(notice, file, 7L));
        assertEquals(30, file.getNoticeAttachmentId());
        assertEquals(10, file.getNoticeId());
        var histories = ArgumentCaptor.forClass(NoticeHistory.class);
        verify(dao, times(2)).insertNoticeHistory(histories.capture());
        NoticeHistory history = histories.getAllValues().get(1);
        assertEquals("FILE_REPLACE", history.getChangeTypeCode());
        assertEquals("old-path", history.getFilePath());
        assertEquals(7L, history.getChangedByAdminId());
    }

    @Test
    void firstAttachmentIsInsertedAndRecorded() {
        when(dao.findFilesByNoticeId(10)).thenReturn(List.of());
        when(dao.nextAttachmentId()).thenReturn(31);
        NoticeFiles file = new NoticeFiles();
        file.setOriginalName("new.txt");
        assertTrue(service.updateNoticeWithFile(notice, file, 7L));
        assertEquals(31, file.getNoticeAttachmentId());
        verify(dao).addfile(List.of(file));
        var histories = ArgumentCaptor.forClass(NoticeHistory.class);
        verify(dao, times(2)).insertNoticeHistory(histories.capture());
        assertEquals("FILE_ADD", histories.getAllValues().get(1).getChangeTypeCode());
        assertEquals("new.txt", histories.getAllValues().get(1).getOriginalName());
    }

    @Test
    void fileFailureRollsBackTheCombinedTransaction() {
        when(dao.findFilesByNoticeId(10)).thenReturn(List.of(new NoticeFiles()));
        when(dao.updateNoticeFile(any())).thenThrow(new IllegalStateException("file update failed"));
        PlatformTransactionManager transactions = mock(PlatformTransactionManager.class);
        TransactionStatus status = mock(TransactionStatus.class);
        when(transactions.getTransaction(any())).thenReturn(status);
        ProxyFactory factory = new ProxyFactory(service);
        factory.setProxyTargetClass(true);
        TransactionInterceptor advice = new TransactionInterceptor();
        advice.setTransactionManager(transactions);
        advice.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
        factory.addAdvice(advice);
        NoticeService transactional = (NoticeService) factory.getProxy();

        assertThrows(IllegalStateException.class,
                () -> transactional.updateNoticeWithFile(notice, new NoticeFiles(), 7L));
        verify(dao).updateNotice(same(notice), anyString());
        verify(transactions).rollback(status);
        verify(transactions, never()).commit(any());
    }

    @Test
    void deletionRecordsOldFileAndScopesDeleteToNotice() {
        NoticeFiles old = new NoticeFiles();
        old.setNoticeAttachmentId(30);
        old.setOriginalName("old.txt");
        old.setFilePath("old-path");
        when(dao.findFilesByNoticeId(10)).thenReturn(List.of(old));
        when(dao.deleteNoticeFile(10, 30)).thenReturn(1);
        assertTrue(service.updateNoticeRemovingFile(notice, 7L));
        verify(dao).deleteNoticeFile(10, 30);
        var histories = ArgumentCaptor.forClass(NoticeHistory.class);
        verify(dao, times(2)).insertNoticeHistory(histories.capture());
        NoticeHistory deleted = histories.getAllValues().get(1);
        assertEquals("FILE_DELETE", deleted.getChangeTypeCode());
        assertEquals("old-path", deleted.getFilePath());
        assertEquals(7L, deleted.getChangedByAdminId());
    }

    @Test
    void deletingAbsentFileIsSafe() {
        when(dao.findFilesByNoticeId(10)).thenReturn(List.of());
        assertTrue(service.updateNoticeRemovingFile(notice, 7L));
        verify(dao, never()).deleteNoticeFile(anyInt(), anyInt());
    }

    @Test
    void deletionFailureRollsBackContentAndHistory() {
        NoticeFiles old = new NoticeFiles();
        old.setNoticeAttachmentId(30);
        when(dao.findFilesByNoticeId(10)).thenReturn(List.of(old));
        // 삭제된 행이 0개인 경우에도 수정 전체를 실패 처리합니다.
        when(dao.deleteNoticeFile(10, 30)).thenReturn(0);
        PlatformTransactionManager transactions = mock(PlatformTransactionManager.class);
        TransactionStatus status = mock(TransactionStatus.class);
        when(transactions.getTransaction(any())).thenReturn(status);
        ProxyFactory factory = new ProxyFactory(service);
        factory.setProxyTargetClass(true);
        TransactionInterceptor advice = new TransactionInterceptor();
        advice.setTransactionManager(transactions);
        advice.setTransactionAttributeSource(new AnnotationTransactionAttributeSource());
        factory.addAdvice(advice);
        NoticeService transactional = (NoticeService) factory.getProxy();
        assertThrows(IllegalStateException.class, () -> transactional.updateNoticeRemovingFile(notice, 7L));
        verify(transactions).rollback(status);
        verify(transactions, never()).commit(any());
    }
}
