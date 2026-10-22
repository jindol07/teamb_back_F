package kr.co.alpharking.controller.notification;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.entity.notification.NotificationEntity;
import kr.co.alpharking.service.notification.NotificationService;

@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

	private final NotificationService notificationService;

	public NotificationController(NotificationService notificationService) {
		this.notificationService = notificationService;
	}

	// 전체 알림 조회
	@GetMapping
	public ResponseEntity<List<NotificationEntity>> getNotifications(@RequestParam String recipienttypecode,
			@RequestParam Long recipientid) {

		return ResponseEntity.ok(notificationService.getNotifications(recipienttypecode, recipientid));
	}

	// 읽지 않은 알림 조회
	@GetMapping("/unread")
	public ResponseEntity<List<NotificationEntity>> getUnreadNotifications(@RequestParam String recipienttypecode,
			@RequestParam Long recipientid) {

		return ResponseEntity.ok(notificationService.getUnreadNotifications(recipienttypecode, recipientid));
	}

	// 읽지 않은 알림 개수 조회
	@GetMapping("/unread/count")
	public ResponseEntity<Map<String, Long>> getUnreadCount(@RequestParam String recipienttypecode,
			@RequestParam Long recipientid) {

		long count = notificationService.getUnreadCount(recipienttypecode, recipientid);

		return ResponseEntity.ok(Map.of("count", count));
	}

	// 알림 읽음 처리
	@PostMapping("/{notificationid}/read")
	public ResponseEntity<Void> markAsRead(@PathVariable Long notificationid, @RequestParam String recipienttypecode,
			@RequestParam Long recipientid) {

		notificationService.markAsRead(notificationid, recipienttypecode, recipientid);

		return ResponseEntity.noContent().build();
	}
}