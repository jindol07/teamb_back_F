
package kr.co.alpharking.service.notification;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.dao.notification.NotificationDao;
import kr.co.alpharking.dto.notification.NotificationDto;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class NotificationService {

    private final NotificationDao notificationDao;

    // 사무실별 알림 목록 조회
    public List<NotificationDto> getNotificationList(Long office_id) {
        return notificationDao.selectNotificationList(office_id);
    }

    // 알림 상세 조회
    public NotificationDto getNotification(Long notification_id) {
        return notificationDao.selectNotificationById(notification_id);
    }

    // 알림 등록
    @Transactional
    public int createNotification(NotificationDto notificationDto) {
        return notificationDao.insertNotification(notificationDto);
    }

    // 알림 읽음 처리
    @Transactional
    public int markAsRead(Long notification_id) {
        return notificationDao.updateReadYn(notification_id);
    }

    // 알림 삭제
    @Transactional
    public int deleteNotification(Long notification_id) {
        return notificationDao.deleteNotification(notification_id);
    }
}
