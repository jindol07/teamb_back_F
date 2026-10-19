package kr.co.alpharking.controller.notice;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.nio.file.Path;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.HttpStatus;
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
