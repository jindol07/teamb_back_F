package kr.co.alpharking.service.vehicle;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.dao.vehicle.VehicleChangeRequestDao;
import kr.co.alpharking.dto.vehicle.VehicleChangeRequestDTO;

@Service
@Transactional
public class VehicleChangeRequestService {

	private final VehicleChangeRequestDao vehicleChangeRequestDao;

	public VehicleChangeRequestService(VehicleChangeRequestDao vehicleChangeRequestDao) {
		this.vehicleChangeRequestDao = vehicleChangeRequestDao;
	}

	// 차량 변경 요청 등록
	public void addVehicleChangeRequest(VehicleChangeRequestDTO vehicleChangeRequest) {

		vehicleChangeRequestDao.add(vehicleChangeRequest);
	}

	// 차량 변경 요청 검토 (승인 / 반려)
	public void updateVehicleChangeRequest(VehicleChangeRequestDTO vehicleChangeRequest) {

		String status = vehicleChangeRequest.getRequeststatuscode();

		if (!"APPROVED".equals(status) && !"REJECTED".equals(status)) {
			throw new IllegalArgumentException("검토 상태는 APPROVED 또는 REJECTED만 가능합니다.");
		}

		if (vehicleChangeRequest.getVehiclechangerequestid() == null) {
			throw new IllegalArgumentException("차량 변경 요청 ID는 필수입니다.");
		}

		if (vehicleChangeRequest.getRevieweradminid() == null) {
			throw new IllegalArgumentException("검토자 관리자 ID는 필수입니다.");
		}

		vehicleChangeRequestDao.update(vehicleChangeRequest);
	}

	// 차량 변경 요청 목록 조회
	@Transactional(readOnly = true)
	public List<VehicleChangeRequestDTO> getVehicleChangeRequests() {
		return vehicleChangeRequestDao.list();
	}

	// 차량 변경 요청 취소
	public void deleteVehicleChangeRequest(Long vehicleChangeRequestId) {

		if (vehicleChangeRequestId == null) {
			throw new IllegalArgumentException("차량 변경 요청 ID는 필수입니다.");
		}

		vehicleChangeRequestDao.delete(vehicleChangeRequestId);
	}

	// 실제 차량 변경 적용 완료 기록
	public void markVehicleChangeRequestApplied(Long vehicleChangeRequestId) {

		if (vehicleChangeRequestId == null) {
			throw new IllegalArgumentException("차량 변경 요청 ID는 필수입니다.");
		}

		vehicleChangeRequestDao.markApplied(vehicleChangeRequestId);
	}
}