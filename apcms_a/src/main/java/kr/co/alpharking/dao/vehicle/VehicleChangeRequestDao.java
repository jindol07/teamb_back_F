package kr.co.alpharking.dao.vehicle;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import kr.co.alpharking.dto.vehicle.VehicleChangeRequestDTO;

@Mapper
public interface VehicleChangeRequestDao {

	// 차량 변경 요청 등록
	void add(VehicleChangeRequestDTO vehicleChangeRequest);

	// ADD 검토 완료 시 차량 행을 만들고, ADD 요청의 검토 이력을 기록
	int addReviewedAddVehicle(VehicleChangeRequestDTO vehicleChangeRequest);

	int addReviewedAddHistory(VehicleChangeRequestDTO vehicleChangeRequest);

	// 기존 차량 요청 검토 결과 적용
	int applyAddReviewToVehicle(VehicleChangeRequestDTO vehicleChangeRequest);

	VehicleChangeRequestDTO findById(@Param("vehiclechangerequestid") Long vehicleChangeRequestId);

	// 차량 변경 요청 검토 처리 (승인 / 반려)
	int update(VehicleChangeRequestDTO vehicleChangeRequest);

	// 기존 차량 검토 이력의 유효 기간 종료 및 새 스냅샷 추가
	void closeReviewHistory(VehicleChangeRequestDTO vehicleChangeRequest);

	int addReviewHistory(VehicleChangeRequestDTO vehicleChangeRequest);

	// 차량 요청 목록 조회
	List<VehicleChangeRequestDTO> list();

	// 차량 변경 요청 취소
	void delete(@Param("vehicle_change_request_id") Long vehicleChangeRequestId);

	// 실제 차량 변경 적용 완료 처리
	void markApplied(@Param("vehicle_change_request_id") Long vehicleChangeRequestId);
	
	// 반려 감사 로그 등록
	int addRejectAuditLog(VehicleChangeRequestDTO vehicleChangeRequest);
	
	// 검토 후 생성된 차량 ID를 요청 데이터에 연결
	int updateTargetVehicleId(VehicleChangeRequestDTO vehicleChangeRequest);
}
