package kr.co.alpharking.controller.notice;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.nio.file.Path;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.notice.NoticeService;

class NoticeControllerTest {
    @TempDir
    Path uploadDir;

    private NoticeController controller;
    private NoticeService service;

    @BeforeEach
    void setUp() {
        service = mock(NoticeService.class);
        controller = new NoticeController();
        ReflectionTestUtils.setField(controller, "noticeService", service);
        ReflectionTestUtils.setField(controller, "filePath", uploadDir.toString());
    }

    private Authentication adminAuthentication(long adminId) {
        Admin admin = new Admin();
        admin.setAdmin_id(adminId);
        return new UsernamePasswordAuthenticationToken(admin, null, admin.getAuthorities());
    }

    @Test
    void multipleAttachmentsAreRejectedBeforeAnyFileOrDatabaseWrite() {
        MultipartFile first = new MockMultipartFile("files", "a.txt", "text/plain", new byte[] {1});
        MultipartFile second = new MockMultipartFile("files", "b.txt", "text/plain", new byte[] {2});

        var response = controller.addNotice(new NoticeCreateReq(), new MultipartFile[] {first, second}, adminAuthentication(7));

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        assertEquals("첨부파일은 1개만 등록할 수 있습니다.", response.getBody());
        assertFalse(Files.exists(uploadDir.resolve("notice")));
        verifyNoInteractions(service);
    }

    @Test
    void oneAttachmentAndEmptyPlaceholderAreAccepted() throws Exception {
        MultipartFile empty = new MockMultipartFile("files", "", "application/octet-stream", new byte[0]);
        MultipartFile file = new MockMultipartFile("files", "a.txt", "text/plain", "notice".getBytes(StandardCharsets.UTF_8));
        NoticeCreateReq request = new NoticeCreateReq();

        var response = controller.addNotice(request, new MultipartFile[] {empty, file}, adminAuthentication(7));

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertEquals(1, request.getGetfilelist().size());
        assertEquals("notice", Files.readString(Path.of(request.getGetfilelist().get(0).getFilePath())));
        verify(service).transcationProcess(same(request), anyList());
    }

    @Test
    void authenticatedAdminCanReadHistory() {
        when(service.getNoticeHistoryList(10)).thenReturn(List.of());
        assertEquals(HttpStatus.OK, controller.getNoticeHistoryList(10, adminAuthentication(7)).getStatusCode());
        verify(service).getNoticeHistoryList(10);
    }

    @Test
    void unauthenticatedHistoryNeverReachesService() {
        assertEquals(HttpStatus.UNAUTHORIZED, assertThrows(ResponseStatusException.class,
                () -> controller.getNoticeHistoryList(10, null)).getStatusCode());
        verifyNoInteractions(service);
    }

    @Test
    void officeAndForgedAdminPrincipalsCannotReadHistory() {
        Authentication office = new UsernamePasswordAuthenticationToken("user", null,
                List.of(new SimpleGrantedAuthority("OFFICE")));
        Authentication forgedAdmin = new UsernamePasswordAuthenticationToken("user", null,
                List.of(new SimpleGrantedAuthority("ADMIN")));
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                () -> controller.getNoticeHistoryList(10, office)).getStatusCode());
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                () -> controller.getNoticeHistoryList(10, forgedAdmin)).getStatusCode());
        verifyNoInteractions(service);
    }

    @Test
    void registrationOverridesSubmittedWriterWithAuthenticatedAdmin() {
        NoticeCreateReq request = new NoticeCreateReq();
        request.setWriterAdminId(1);

        assertEquals(HttpStatus.OK, controller.addNotice(request, null, adminAuthentication(7)).getStatusCode());
        assertEquals(7, request.getWriterAdminId());
        verify(service).transcationProcess(same(request), anyList());
    }

    @Test
    void updateAndDeleteUseCurrentAdminForHistory() {
        NoticeCreateReq request = new NoticeCreateReq();
        when(service.updateNotice(request, 7L)).thenReturn(true);
        when(service.deleteNotice(10, 8L)).thenReturn(true);

        assertEquals(HttpStatus.OK, controller.updateNotice(10, request, adminAuthentication(7)).getStatusCode());
        assertEquals(HttpStatus.OK, controller.deleteNotice(10, adminAuthentication(8)).getStatusCode());
        assertEquals(10, request.getNoticeId());
        verify(service).updateNotice(request, 7L);
        verify(service).deleteNotice(10, 8L);
    }

    @Test
    void unauthenticatedWritesNeverReachService() {
        NoticeCreateReq request = new NoticeCreateReq();
        assertEquals(HttpStatus.UNAUTHORIZED, assertThrows(ResponseStatusException.class,
                () -> controller.addNotice(request, null, null)).getStatusCode());
        assertEquals(HttpStatus.UNAUTHORIZED, assertThrows(ResponseStatusException.class,
                () -> controller.updateNotice(10, request, null)).getStatusCode());
        assertEquals(HttpStatus.UNAUTHORIZED, assertThrows(ResponseStatusException.class,
                () -> controller.deleteNotice(10, null)).getStatusCode());
        verifyNoInteractions(service);
    }

    @Test
    void nonAdminPrincipalCannotWrite() {
        Authentication authentication = new UsernamePasswordAuthenticationToken("user", null,
                List.of(new SimpleGrantedAuthority("OFFICE")));
        assertEquals(HttpStatus.FORBIDDEN, assertThrows(ResponseStatusException.class,
                () -> controller.deleteNotice(10, authentication)).getStatusCode());
        verifyNoInteractions(service);
    }
}
