package kr.co.alpharking.service.vehiclehistory;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.dao.vehiclehistory.VehiclehistoryDao;
import kr.co.alpharking.dto.vehiclehistory.VehiclehistoryDto;

@Service
public class VehiclehistoryService {

    private final VehiclehistoryDao vehiclehistoryDao;

    public VehiclehistoryService(VehiclehistoryDao vehiclehistoryDao) {
        this.vehiclehistoryDao = vehiclehistoryDao;
    }

    @Transactional(readOnly = true)
    public List<VehiclehistoryDto> getVehicleHistoryList() {
        return vehiclehistoryDao.list();
    }
}
