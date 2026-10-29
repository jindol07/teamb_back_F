/**
 * 용도: office_history에 저장된 당시 계정 정보와 변경 메타데이터의 조회 응답.
 * 사용처: office-history.xml → OfficeHistoryController → History.tsx.
 * 날짜는 Oracle DATE의 값을 시간대 변환 없이 yyyy-MM-dd HH:mm:ss 문자열로 반환한다.
 */
package kr.co.alpharking.dto.officehistory;

import lombok.Data;
import org.apache.ibatis.type.Alias;

@Data
@Alias("OfficeHistoryRow")
public class OfficeHistoryRow {
    private Long officeHistoryId;
    private Long officeId;
    private Long companyId;
    private Integer floorNo;
    private String officeNumber;
    private String loginId;
    private String email;
    private String phone;
    private String statusCode;
    private String createdAt;
    private String updatedAt;
    private String withdrawnAt;
    private Long changedByAdminId;
    private String actorTypeCode;
    private Long actorId;
    private String changeTypeCode;
    private String changeReason;
    private String validFrom;
    private String validTo;
}
