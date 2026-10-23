/** [1023_1010] 파일 안내
 * 용도: 관리자 패널의 구획 변경 이력 조회 결과.
 * 사용처·연결: parking-space.xml.findHistory → ParkingSpaceService.correctionDetail → SlotDetailPanel.
 * changeReason은 DB에 저장된 사유다. 관리자 ID·변경 출처·유효 구간을 함께 표시한다.
 */
package kr.co.alpharking.dto.parking;

import lombok.Data;
import org.apache.ibatis.type.Alias;

/** 관리자 패널 전용 구획 이력. 기존 테이블을 조회하며 스키마를 추가하지 않는다. */
@Data
@Alias("ParkingSpaceHistoryRow")
public class ParkingSpaceHistoryRow {
    // [1023_1010] 구획 변경 이력 PK. 조회 기준 충돌 검사와 이력 식별에 사용한다.
    private Long parkingSpaceHistoryId;
    // [1023_1010] 서버 구획 상태 코드. 공개 조회에서는 예약이 반영된 표시 상태일 수 있다.
    private String spaceStatusCode;
    // [1023_1010] 일반·전기차·장애인 등 구획 종류 코드. 점유 상태와 별개다.
    private String spaceTypeCode;
    // [1023_1010] 관리자 메모 또는 이력 시점의 메모. 사용자 공개 DTO에는 없다.
    private String memo;
    // [1023_1010] 필수 변경 사유. 이력에는 보정 전후 정보와 합친 사유가 저장될 수 있다.
    private String changeReason;
    // [1023_1010] 변경 당시 관리자 PK. AI 이력에서는 null일 수 있다.
    private Long changedByAdminId;
    // [1023_1010] ADMIN·AI 등 변경 출처 코드.
    private String changeSourceCode;
    // [1023_1010] 이력의 유효 시작 시각.
    private String validFrom;
    // [1023_1010] 이력 유효 종료 시각. 열린 이력은 null일 수 있다.
    private String validTo;
}
