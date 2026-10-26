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

    @Transactional
    public NotificationEntity createNotification(String recipienttypecode, Long recipientid,
            String notificationtypecode, String message, Long targetid) {
        NotificationEntity notification;
        if ("USER".equalsIgnoreCase(recipienttypecode)) {
            notification = new NotificationEntity(notificationtypecode, notificationtypecode, message,
                    recipientid, null, null, null, targetid, null);
        } else if ("ADMIN".equalsIgnoreCase(recipienttypecode)) {
            notification = new NotificationEntity(notificationtypecode, notificationtypecode, message,
                    null, recipientid, null, null, targetid, null);
        } else {
            throw new IllegalArgumentException("지원하지 않는 알림 수신자 유형입니다.");
        }
        return notificationRepository.save(notification);
    }

    public List<NotificationEntity> getNotifications(String recipienttypecode, Long recipientid) {
        if ("USER".equalsIgnoreCase(recipienttypecode)) {
            return notificationRepository.findByOfficeIdOrderByCreatedatDesc(recipientid);
        }
        if ("ADMIN".equalsIgnoreCase(recipienttypecode)) {
            return notificationRepository.findByAdminIdOrderByCreatedatDesc(recipientid);
        }
        return List.of();
    }

    public List<NotificationEntity> getUnreadNotifications(String recipienttypecode, Long recipientid) {
        if ("USER".equalsIgnoreCase(recipienttypecode)) {
            return notificationRepository.findByOfficeIdAndReadyNOrderByCreatedatDesc(recipientid, "N");
        }
        if ("ADMIN".equalsIgnoreCase(recipienttypecode)) {
            return notificationRepository.findByAdminIdAndReadyNOrderByCreatedatDesc(recipientid, "N");
        }
        return List.of();
    }

    public long getUnreadCount(String recipienttypecode, Long recipientid) {
        if ("USER".equalsIgnoreCase(recipienttypecode)) {
            return notificationRepository.countByOfficeIdAndReadyN(recipientid, "N");
        }
        if ("ADMIN".equalsIgnoreCase(recipienttypecode)) {
            return notificationRepository.countByAdminIdAndReadyN(recipientid, "N");
        }
        return 0;
    }

    @Transactional
    public void markAsRead(Long notificationid, String recipienttypecode, Long recipientid) {
        NotificationEntity notification = notificationRepository.findById(notificationid)
                .orElseThrow(() -> new IllegalArgumentException("알림을 찾을 수 없습니다."));

        boolean authorized = "USER".equalsIgnoreCase(recipienttypecode)
                ? recipientid.equals(notification.getOfficeId())
                : "ADMIN".equalsIgnoreCase(recipienttypecode)
                        && recipientid.equals(notification.getAdminId());
        if (!authorized) {
            throw new IllegalArgumentException("해당 알림에 접근할 권한이 없습니다.");
        }
        notification.markAsRead();
    }
}
