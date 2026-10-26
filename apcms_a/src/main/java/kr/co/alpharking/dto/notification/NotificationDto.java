package kr.co.alpharking.dto.notification;

import java.util.Date;

import org.apache.ibatis.type.Alias;

import lombok.Getter;
import lombok.Setter;

@Alias("noti")
@Setter
@Getter
public class NotificationDto {
	
	private Long notification_id; // 알림 식별자
	// N:1 office 관계
	private Long office_id; // 수신 사무실
	private String notification_type_code; // RESERVATION/REPORT/NOTICE/ETC
	private String title; // 알림 제목
	private String content; // 알림 내용
	private String read_yn; // 읽음 여부 Y/N
	private Date created_at; // 생성일시
	private Date read_at;
	private Long vehicle_change_request_id; // 차량 변경 신청 ID
}