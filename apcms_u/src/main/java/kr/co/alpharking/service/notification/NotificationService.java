
package kr.co.alpharking.service.notification;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.entity.notification.NotificationEntity;
import kr.co.alpharking.repository.notification.NotificationRepository;

@Service
@Transactional(readOnly = true)
public class NotificationService {

	private final NotificationRepository notificationRepository;

	public NotificationService(NotificationRepository notificationRepository) {
		this.notificationRepository = notificationRepository;
	}

	// 알림 생성 및 저장
	@Transactional
	public NotificationEntity createNotification(String recipienttypecode, Long recipientid,
			String notificationtypecode, String message, Long targetid) {

		if (!"ADMIN".equalsIgnoreCase(recipienttypecode)) {
			throw new IllegalArgumentException("현재 알림 엔티티에서는 관리자 알림만 생성할 수 있습니다.");
		}

		NotificationEntity notification = new NotificationEntity(notificationtypecode, notificationtypecode, message,
				null, recipientid, null, null, null, null);

		return notificationRepository.save(notification);
	}

	// 수신자별 전체 알림 조회
	public List<NotificationEntity> getNotifications(String recipienttypecode, Long recipientid) {

		if (!"ADMIN".equalsIgnoreCase(recipienttypecode)) {
			return List.of();
		}

		return notificationRepository.findByAdminIdOrderByCreatedatDesc(recipientid);
	}

	// 수신자별 읽지 않은 알림 조회
	public List<NotificationEntity> getUnreadNotifications(String recipienttypecode, Long recipientid) {

		if (!"ADMIN".equalsIgnoreCase(recipienttypecode)) {
			return List.of();
		}

		return notificationRepository.findByAdminIdAndReadyNOrderByCreatedatDesc(recipientid, "N");
	}

	// 읽지 않은 알림 개수 조회
	public long getUnreadCount(String recipienttypecode, Long recipientid) {

		if (!"ADMIN".equalsIgnoreCase(recipienttypecode)) {
			return 0;
		}

		return notificationRepository.countByAdminIdAndReadyN(recipientid, "N");
	}

	// 알림 읽음 처리
	@Transactional
	public void markAsRead(Long notificationid, String recipienttypecode, Long recipientid) {

		if (!"ADMIN".equalsIgnoreCase(recipienttypecode)) {
			throw new IllegalArgumentException("해당 알림에 접근할 권한이 없습니다.");
		}

		NotificationEntity notification = notificationRepository.findById(notificationid)
				.orElseThrow(() -> new IllegalArgumentException("알림을 찾을 수 없습니다."));

		// 다른 사용자의 알림을 읽음 처리하지 못하도록 확인
		if (notification.getAdminId() == null || !notification.getAdminId().equals(recipientid)) {
			throw new IllegalArgumentException("해당 알림에 접근할 권한이 없습니다.");
		}

		notification.markAsRead();
	}
}
