package kr.co.alpharking.service.vehiclepenalty;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.dao.vehiclepenalty.VehiclePenaltyDao;
import kr.co.alpharking.dto.vehiclepenalty.VehiclePenaltyDto;

@Service
@Transactional
public class VehiclepenaltyService {

	private final VehiclePenaltyDao vehiclePenaltyDao;

	public VehiclepenaltyService(VehiclePenaltyDao vehiclePenaltyDao) {
		this.vehiclePenaltyDao = vehiclePenaltyDao;
	}

	public void addVehiclePenalty(VehiclePenaltyDto vehiclePenalty) {
		validateForAdd(vehiclePenalty);
		vehiclePenaltyDao.add(vehiclePenalty);
	}

	@Transactional(readOnly = true)
	public List<VehiclePenaltyDto> getVehiclePenalties() {
		return vehiclePenaltyDao.list();
	}

	public void updateVehiclePenalty(VehiclePenaltyDto vehiclePenalty) {
		if (vehiclePenalty == null || vehiclePenalty.getVehiclepenaltyid() == null) {
			throw new IllegalArgumentException("패널티 식별자는 필수입니다.");
		}
        if (vehiclePenalty.getVehicleid() == null) {
            throw new IllegalArgumentException("차량 식별자는 필수입니다.");
        }
		if (vehiclePenalty.getViolationtypecode() == null || vehiclePenalty.getViolationtypecode().isBlank()) {
			throw new IllegalArgumentException("위반 유형은 필수입니다.");
		}
		if (vehiclePenalty.getPenaltyamount() < 0) {
			throw new IllegalArgumentException("벌칙금은 0 이상이어야 합니다.");
		}
		vehiclePenaltyDao.update(vehiclePenalty);
	}

	public void deleteVehiclePenalty(Long vehiclePenaltyId) {
		if (vehiclePenaltyId == null) {
			throw new IllegalArgumentException("패널티 식별자는 필수입니다.");
		}
		vehiclePenaltyDao.delete(vehiclePenaltyId);
	}

	private void validateForAdd(VehiclePenaltyDto vehiclePenalty) {
		if (vehiclePenalty == null) {
			throw new IllegalArgumentException("패널티 정보는 필수입니다.");
		}
		if (vehiclePenalty.getVehicleid() == null) {
			throw new IllegalArgumentException("차량 식별자는 필수입니다.");
		}
		if (vehiclePenalty.getImposedbyadminid() == null) {
			throw new IllegalArgumentException("부과 관리자 식별자는 필수입니다.");
		}
		if (vehiclePenalty.getViolationtypecode() == null || vehiclePenalty.getViolationtypecode().isBlank()) {
			throw new IllegalArgumentException("위반 유형은 필수입니다.");
		}
		if (vehiclePenalty.getPenaltyamount() < 0) {
			throw new IllegalArgumentException("벌칙금은 0 이상이어야 합니다.");
		}
	}
}
