
package kr.co.alpharking.dao.notification;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import kr.co.alpharking.dto.notification.NotificationDto;

@Mapper
public interface NotificationDao {

	// 사무실별 알림 목록 조회
	List<NotificationDto> selectNotificationList(@Param("office_id") Long office_id);

	// 알림 상세 조회
	NotificationDto selectNotificationById(@Param("notification_id") Long notification_id);

	// 알림 등록
	int insertNotification(NotificationDto notificationDto);

	// 알림 읽음 처리
	int updateReadYn(@Param("notification_id") Long notification_id);

	// 알림 삭제
	int deleteNotification(@Param("notification_id") Long notification_id);
}