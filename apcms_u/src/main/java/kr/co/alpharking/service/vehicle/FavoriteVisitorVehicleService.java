package kr.co.alpharking.service.vehicle;

import kr.co.alpharking.entity.vehicle.FavoriteVisitorVehicle;
import kr.co.alpharking.repository.vehicle.FavoriteVisitorVehicleRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class FavoriteVisitorVehicleService {

    private final FavoriteVisitorVehicleRepository vehicleRepository;

    // 즐겨찾는 방문자 등록
    @Transactional
    public Long registerVehicle(Long officeId, String vehicleNumber, String aliasName) {
        FavoriteVisitorVehicle vehicle = FavoriteVisitorVehicle.builder()
                .officeId(officeId)
                .vehicleNumber(vehicleNumber)
                .aliasName(aliasName)
                .build();

        FavoriteVisitorVehicle savedVehicle = vehicleRepository.save(vehicle);
        return savedVehicle.getFavoriteVisitorVehicleId();
    }

    // 특정 오피스의 방문자 차량 목록 조회
    public List<FavoriteVisitorVehicle> getVehiclesByOffice(Long officeId) {
        return vehicleRepository.findByOfficeId(officeId);
    }
}