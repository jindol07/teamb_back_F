package kr.co.alpharking.service.vehicle;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dto.vehicle.VehicleRegistrationRequestDto;
import kr.co.alpharking.entity.vehicle.Vehicle;
import kr.co.alpharking.entity.vehicle.VehicleChangeRequest;
import kr.co.alpharking.repository.vehicle.VehicleChangeRequestRepository;
import kr.co.alpharking.service.notification.NotificationService;
import kr.co.alpharking.repository.vehicle.VehicleRepository;

@Service
public class VehicleService {
    private static final List<String> ACTIVE_REGISTRATION_STATUSES = List.of("REGISTERED", "APPROVED");

    @Autowired
    private VehicleRepository vehicleRepository;

    @Autowired
    private VehicleChangeRequestRepository vehicleChangeRequestRepository;

    @Autowired
    private NotificationService notificationService;

    public List<Vehicle> getVehiclesByOffice(Long officeId) {
        return vehicleRepository.findByOfficeIdAndDeletedAtIsNullAndRegistrationStatusCodeIn(
                officeId, ACTIVE_REGISTRATION_STATUSES);
    }

    @Transactional
    public void submitVehicleRegistrationRequest(Long officeId, VehicleRegistrationRequestDto request) {
        if (request == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "차량 정보를 입력해주세요.");
        }
        String vehicleNumber = request.getVehicleNumber() == null ? "" : request.getVehicleNumber().trim();
        String vehicleModel = request.getVehicleModel() == null ? "" : request.getVehicleModel().trim();
        String ownerName = request.getOwnerName() == null ? "" : request.getOwnerName().trim();
        if (vehicleNumber.isEmpty() || ownerName.isEmpty() || vehicleModel.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "차량번호, 차주명과 차종을 입력해주세요.");
        }
        if (vehicleRepository.existsByVehicleNumberAndRegistrationStatusCodeInAndDeletedAtIsNull(
                vehicleNumber, ACTIVE_REGISTRATION_STATUSES)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 등록된 차량번호입니다.");
        }
        if (vehicleChangeRequestRepository.existsByOfficeIdAndRequestedVehicleNumberAndRequestStatusCode(
                officeId, vehicleNumber, "REQUESTED")) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 처리 중인 차량 등록 신청입니다.");
        }
        VehicleChangeRequest vehicleRequest = new VehicleChangeRequest();
        vehicleRequest.setOfficeId(officeId);
        vehicleRequest.setRequestTypeCode("ADD");
        vehicleRequest.setRequestedVehicleNumber(vehicleNumber);
        vehicleRequest.setRequestedOwnerName(ownerName);
        vehicleRequest.setRequestedVehicleModel(vehicleModel);
        vehicleRequest.setRequestedVehicleTypeCode("PERSONAL");
        vehicleRequest.setRequestReason("마이페이지 차량 등록 신청");
        vehicleRequest.setRequestStatusCode("REQUESTED");
        vehicleRequest.setRequestedAt(LocalDateTime.now());
        VehicleChangeRequest savedRequest = vehicleChangeRequestRepository.save(vehicleRequest);
        notificationService.createNotification("USER", officeId, "VEHICLE_REQUEST",
                "차량 등록 신청이 접수되었습니다. 관리자 검토 후 결과를 알려드릴게요.",
                savedRequest.getVehicleChangeRequestId());
    }

    public Optional<Vehicle> findByVehicleNumber(String vehicleNumber) {
        return vehicleRepository.findByVehicleNumber(vehicleNumber);
    }

    public List<Vehicle> searchByVehicleNumber(String vehicleNumber) {
        if (vehicleNumber == null || vehicleNumber.isBlank()) {
            return List.of();
        }
        return vehicleRepository.searchByVehicleNumberContaining(vehicleNumber.trim());
    }

    public Optional<Vehicle> findRegisteredVehicleByNumber(String vehicleNumber) {
        return vehicleRepository.findByVehicleNumberAndRegistrationStatusCodeAndDeletedAtIsNull(
                vehicleNumber, "REGISTERED");
    }

    @Transactional
    public void deleteVehicle(Long vehicleId, Long officeId) {
        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "차량을 찾을 수 없습니다."));

        if (vehicle.getOfficeId() == null || !vehicle.getOfficeId().equals(officeId)) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "삭제 권한이 없습니다.");
        }
        if (vehicle.getDeletedAt() != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "차량이 이미 삭제되었습니다.");
        }
        if (!ACTIVE_REGISTRATION_STATUSES.contains(vehicle.getRegistrationStatusCode())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "등록 완료된 차량만 삭제할 수 있습니다.");
        }
        if (vehicleRepository.countByOfficeIdAndDeletedAtIsNullAndRegistrationStatusCodeIn(
                officeId, ACTIVE_REGISTRATION_STATUSES) <= 1) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "최소 1대의 차량은 등록되어 있어야 합니다.");
        }

        vehicle.setDeletedAt(LocalDateTime.now());
        vehicleRepository.save(vehicle);
    }
}
