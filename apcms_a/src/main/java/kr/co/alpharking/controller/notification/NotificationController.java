
package kr.co.alpharking.controller.notification;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import kr.co.alpharking.dto.notification.NotificationDto;
import kr.co.alpharking.service.notification.NotificationService;

import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;

    // 1. 사무실별 알림 목록 조회
    // GET /api/notifications/office/1
    @GetMapping("/office/{office_id}")
    public ResponseEntity<List<NotificationDto>> getNotificationList(
            @PathVariable("office_id") Long office_id) {

        List<NotificationDto> list =
                notificationService.getNotificationList(office_id);

        return ResponseEntity.ok(list);
    }

    // 2. 알림 상세 조회
    // GET /api/notifications/1
    @GetMapping("/{notification_id}")
    public ResponseEntity<NotificationDto> getNotification(
            @PathVariable("notification_id") Long notification_id) {

        NotificationDto notification =
                notificationService.getNotification(notification_id);

        if (notification == null) {
            return ResponseEntity.notFound().build();
        }

        return ResponseEntity.ok(notification);
    }

    // 3. 알림 등록
    // POST /api/notifications
    @PostMapping
    public ResponseEntity<NotificationDto> createNotification(
            @RequestBody NotificationDto notificationDto) {

        notificationService.createNotification(notificationDto);

        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(notificationDto);
    }

    // 4. 알림 읽음 처리
    // PATCH /api/notifications/1/read
    @PatchMapping("/{notification_id}/read")
    public ResponseEntity<Void> markAsRead(
            @PathVariable("notification_id") Long notification_id) {

        int result = notificationService.markAsRead(notification_id);

        if (result == 0) {
            return ResponseEntity.notFound().build();
        }

        return ResponseEntity.noContent().build();
    }

    // 5. 알림 삭제
    // DELETE /api/notifications/1
    @DeleteMapping("/{notification_id}")
    public ResponseEntity<Void> deleteNotification(
            @PathVariable("notification_id") Long notification_id) {

        int result =
                notificationService.deleteNotification(notification_id);

        if (result == 0) {
            return ResponseEntity.notFound().build();
        }

        return ResponseEntity.noContent().build();
    }
}
