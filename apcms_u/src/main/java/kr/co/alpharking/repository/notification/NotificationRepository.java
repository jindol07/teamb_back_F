package kr.co.alpharking.repository.notification;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import kr.co.alpharking.entity.notification.NotificationEntity;

// 알림 저장 및 조회
@Repository
public interface NotificationRepository
        extends JpaRepository<NotificationEntity, Long> {

    // 관리자별 전체 알림 조회
    List<NotificationEntity>
        findByAdminIdOrderByCreatedatDesc(Long adminId);

    // 관리자별 읽지 않은 알림 조회
    List<NotificationEntity>
        findByAdminIdAndReadyNOrderByCreatedatDesc(
            Long adminId,
            String readyN
        );

    // 관리자별 읽지 않은 알림 개수 조회
    long countByAdminIdAndReadyN(Long adminId, String readyN);
}