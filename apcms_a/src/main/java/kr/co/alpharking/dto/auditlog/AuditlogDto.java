package kr.co.alpharking.dto.auditlog;

import java.util.Date;

import org.apache.ibatis.type.Alias;

import lombok.Getter;
import lombok.Setter;

@Alias("audit")
@Setter
@Getter
public class AuditlogDto {
	private Long auditlogid; // 감사 ID
	private String actortypecode; // ADMIN/USER
	private Long actorid; // 유형에 따른 행위자 ID: 범용 논리 참조
	private String actiontypecode; // 업무 작업 유형
	private String targettable; // 대상 테이블
	private Long targetid; // 원본 테이블 PK : 범용 논리 참조
	private String beforedata; // 변경 전 JSON : 비밀정보 제거
	private String afterdata; // 변경 후 JSON : 비밀정보 제거
	private String changereason; // 변경 사유
	private Date occurredat; // 감사 기록 시각
}