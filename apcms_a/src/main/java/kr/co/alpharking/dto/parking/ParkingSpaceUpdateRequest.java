/** [1023_1010] 파일 안내
 * 용도: 구획 보정 저장 요청과 조회 당시 충돌 검사 기준값.
 * 사용처·연결: SlotDetailPanel → saveParkingSpace → ParkingSpaceController → ParkingSpaceService.
 * KEEP/ASSIGN/DETACH/EXIT는 기존 이용 기록 처리 방식이다. expected 값이 현재 DB와 다르면 저장을 거절한다.
 */
package kr.co.alpharking.dto.parking;

import java.util.List;

/** 저장 버튼을 누른 시점에만 전달하는 관리자의 강제 변경 요청. */
public record ParkingSpaceUpdateRequest(
        // [1023_1010] 관리자가 저장하려는 구획 상태 코드. 조회 당시 기준은 expectedStatus로 따로 전달한다.
        String spaceStatusCode,
        // [1023_1010] 일반·전기차·장애인 등 구획 종류 코드. 점유 상태와 별개다.
        String spaceTypeCode,
        // [1023_1010] 관리자가 저장하려는 메모. 변경 사유(changeReason)와는 별도 값이다.
        String memo,
        // [1023_1010] 필수 변경 사유. 이력에는 보정 전후 정보와 합친 사유가 저장될 수 있다.
        String changeReason,
        // [1023_1010] KEEP·ASSIGN·DETACH·EXIT 중 기존 이용 기록 처리 방법.
        String usageAction,
        // [1023_1010] 이용 기록 PK. 기존 미출차 기록 선택·출차·배정의 대상이다.
        Long parkingUsageId,
        // [1023_1010] 선택한 기존 이용 기록의 번호판. 서버가 해당 기록의 실제 번호와 대조한다.
        String vehicleNumber,
        // [1023_1010] EXIT 보정에서 관리자가 입력한 실제 출차 시각. 서버가 시간 순서와 미래 시각을 검증한다.
        String exitAt,
        // [1023_1010] 조회 당시 구획 원본 상태. 서버가 현재 값과 비교한다.
        String expectedStatus,
        // [1023_1010] 조회 당시 구획 종류. 현재 값과 다르면 보정을 거절한다.
        String expectedType,
        // [1023_1010] 조회 당시 관리자 메모.
        String expectedMemo,
        // [1023_1010] 조회 당시 구획 수정 시각.
        String expectedUpdatedAt,
        // [1023_1010] 조회 당시 최신 구획 이력 PK. 같은 초의 변경 감지에도 사용한다.
        Long expectedHistoryId,
        // [1023_1010] 조회 당시 연결된 미출차 기록 ID 목록. 현재 목록과 함께 대조한다.
        List<Long> expectedActiveUsageIds
) {}
