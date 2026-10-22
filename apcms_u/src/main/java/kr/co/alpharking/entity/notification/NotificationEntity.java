
package kr.co.alpharking.entity.notification;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

// JPA 알림 데이터 구조
@Entity
@Table(name = "NOTIFICATION")
public class NotificationEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "NOTIFICATION_ID")
    private Long notificationid; // 알림 ID

    @Column(name = "OFFICE_ID")
    private Long officeId; // 관리 사무소 ID

    @Column(name = "NOTIFICATION_TYPE_CODE")
    private String notificationtypecode; // 알림 유형 코드

    @Column(name = "TITLE")
    private String title; // 알림 제목

    @Column(name = "CONTENT")
    private String content; // 알림 내용

    @Column(name = "READ_YN", columnDefinition = "CHAR")
    private String readyN; // 알림 읽음 여부 (Y/N)

    @Column(name = "CREATED_AT")
    private LocalDateTime createdat; // 알림 생성 시각

    @Column(name = "READ_AT")
    private LocalDateTime readAt; // 알림 읽은 시각

    @Column(name = "ADMIN_ID")
    private Long adminId; // 관리자 ID

    @Column(name = "REPORT_ID")
    private Long reportId; // 신고 ID

    @Column(name = "AI_DETECTION_EVENT_ID")
    private Long aiDetectionEventId; // AI 감지 이벤트 ID

    @Column(name = "VEHICLE_CHANGE_REQUEST_ID")
    private Long vehicleChangeRequestId; // 차량 변경 신청 ID

    @Column(name = "SAFETY_INCIDENT_ID")
    private Long safetyIncidentId; // 안전 사고 ID

    // JPA에서 사용하는 기본 생성자
    protected NotificationEntity() {
    }

    // 알림 생성 및 저장
    public NotificationEntity(
            String notificationtypecode,
            String title,
            String content,
            Long officeId,
            Long adminId,
            Long reportId,
            Long aiDetectionEventId,
            Long vehicleChangeRequestId,
            Long safetyIncidentId) {

        this.notificationtypecode = notificationtypecode;
        this.title = title;
        this.content = content;
        this.officeId = officeId;
        this.adminId = adminId;
        this.reportId = reportId;
        this.aiDetectionEventId = aiDetectionEventId;
        this.vehicleChangeRequestId = vehicleChangeRequestId;
        this.safetyIncidentId = safetyIncidentId;
        this.readyN = "N";
        this.createdat = LocalDateTime.now();
    }

    // 알림 읽음 처리
    public void markAsRead() {
        this.readyN = "Y";
        this.readAt = LocalDateTime.now();
    }

    public Long getNotificationid() {
        return notificationid;
    }

    public Long getOfficeId() {
        return officeId;
    }

    public String getNotificationtypecode() {
        return notificationtypecode;
    }

    public String getTitle() {
        return title;
    }

    public String getContent() {
        return content;
    }

    public String getReadyN() {
        return readyN;
    }

    public LocalDateTime getCreatedat() {
        return createdat;
    }

    public LocalDateTime getReadAt() {
        return readAt;
    }

    public Long getAdminId() {
        return adminId;
    }

    public Long getReportId() {
        return reportId;
    }

    public Long getAiDetectionEventId() {
        return aiDetectionEventId;
    }

    public Long getVehicleChangeRequestId() {
        return vehicleChangeRequestId;
    }

    public Long getSafetyIncidentId() {
        return safetyIncidentId;
    }
}
