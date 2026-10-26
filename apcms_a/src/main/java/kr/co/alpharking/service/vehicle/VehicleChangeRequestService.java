package kr.co.alpharking.service.vehicle;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import kr.co.alpharking.dao.vehicle.VehicleChangeRequestDao;
import kr.co.alpharking.dto.vehicle.VehicleChangeRequestDTO;
import kr.co.alpharking.dto.notification.NotificationDto;
import kr.co.alpharking.service.notification.NotificationService;

@Service
@Transactional
public class VehicleChangeRequestService {

	private final VehicleChangeRequestDao vehicleChangeRequestDao;
	private final NotificationService notificationService;
	private final ObjectMapper objectMapper = new ObjectMapper(); // 직접 생성

	public VehicleChangeRequestService(VehicleChangeRequestDao vehicleChangeRequestDao,
			NotificationService notificationService) {
		this.vehicleChangeRequestDao = vehicleChangeRequestDao;
		this.notificationService = notificationService;
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

		VehicleChangeRequestDTO storedRequest = vehicleChangeRequestDao
				.findById(vehicleChangeRequest.getVehiclechangerequestid());

		if (storedRequest == null) {
			throw new IllegalStateException("차량 변경 요청을 찾을 수 없습니다.");
		}

		// 변경 전 데이터 보관
		String beforeData = toJson(storedRequest);

		int updated = vehicleChangeRequestDao.update(vehicleChangeRequest);

		if (updated == 0) {
			throw new IllegalStateException("요청이 이미 처리되었거나 존재하지 않습니다.");
		}

		if ("ADD".equals(storedRequest.getRequesttypecode())) {

			storedRequest.setRevieweradminid(vehicleChangeRequest.getRevieweradminid());
			storedRequest.setReviewreason(vehicleChangeRequest.getReviewreason());
			storedRequest.setRequeststatuscode(status);

			int created = vehicleChangeRequestDao.addReviewedAddVehicle(storedRequest);

			if (created != 1 || storedRequest.getTargetvehicleid() == null) {
				throw new IllegalStateException("검토된 추가 차량을 생성하지 못했습니다.");
			}

			// ADD 요청은 DB 제약조건에 따라 target_vehicle_id를 연결하지 않습니다.
			// 승인 또는 반려 이력 저장
			int historyCreated = vehicleChangeRequestDao.addReviewedAddHistory(storedRequest);

			if (historyCreated != 1) {
				throw new IllegalStateException("추가 차량 검토 이력을 저장하지 못했습니다.");
			}

			// 반려일 때만 감사 로그 저장
			saveRejectAuditLog(vehicleChangeRequest, beforeData, status);
			notifyOffice(storedRequest, status);

			return;
		}

		vehicleChangeRequestDao.applyAddReviewToVehicle(vehicleChangeRequest);

		vehicleChangeRequestDao.closeReviewHistory(vehicleChangeRequest);

		if (vehicleChangeRequestDao.addReviewHistory(vehicleChangeRequest) != 1) {
			throw new IllegalStateException("차량 검토 이력이 저장되지 않았습니다.");
		}

		// 반려일 때만 감사 로그 저장
		saveRejectAuditLog(vehicleChangeRequest, beforeData, status);
		notifyOffice(storedRequest, status);
	}

	private void notifyOffice(VehicleChangeRequestDTO request, String status) {
		if (!"ADD".equals(request.getRequesttypecode())) {
			return;
		}
		NotificationDto notification = new NotificationDto();
		notification.setOffice_id(request.getOfficeid());
		notification.setNotification_type_code("APPROVED".equals(status)
				? "VEHICLE_APPROVED" : "VEHICLE_REJECTED");
		notification.setTitle("APPROVED".equals(status) ? "차량 등록 승인" : "차량 등록 반려");
		String message = "차량번호 " + request.getRequestedvehiclenumber()
				+ ("APPROVED".equals(status) ? " 등록 신청이 승인되었습니다."
						: " 등록 신청이 반려되었습니다.");
		if ("REJECTED".equals(status) && request.getReviewreason() != null
				&& !request.getReviewreason().isBlank()) {
			message += " 반려 사유: " + request.getReviewreason();
		}
		notification.setContent(message);
		notification.setVehicle_change_request_id(request.getVehiclechangerequestid());
		int inserted = notificationService.createNotification(notification);
		if (inserted != 1) {
			throw new IllegalStateException("차량 검토 결과 알림을 저장하지 못했습니다.");
		}
	}

	// 반려 감사 로그: REJECTED일 때만 호출
	private void saveRejectAuditLog(VehicleChangeRequestDTO request, String beforeData, String status) {

		if (!"REJECTED".equals(status)) {
			return;
		}

		request.setBeforedata(beforeData);
		request.setAfterdata(toJson(request));

		int inserted = vehicleChangeRequestDao.addRejectAuditLog(request);

		if (inserted != 1) {
			throw new IllegalStateException("반려 감사 로그를 저장하지 못했습니다.");
		}
	}

	// 객체를 JSON 문자열로 변환
	private String toJson(VehicleChangeRequestDTO request) {
		try {
			return objectMapper.writeValueAsString(request);
		} catch (JsonProcessingException e) {
			throw new IllegalStateException("차량 변경 요청 데이터를 JSON으로 변환하지 못했습니다.", e);
		}
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