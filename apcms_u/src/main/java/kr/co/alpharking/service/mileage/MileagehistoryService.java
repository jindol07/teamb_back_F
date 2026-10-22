package kr.co.alpharking.service.mileage;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dao.mileage.MileagehistoryDao;
import kr.co.alpharking.dto.mileage.MileagehistoryDto;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.security.UserRepository;

@Service
public class MileagehistoryService {

    private final MileagehistoryDao mileagehistoryDao;
    private final UserRepository userRepository;

    public MileagehistoryService(MileagehistoryDao mileagehistoryDao, UserRepository userRepository) {
        this.mileagehistoryDao = mileagehistoryDao;
        this.userRepository = userRepository;
    }

    @Transactional(readOnly = true)
    public List<MileagehistoryDto> findAll() {
        return mileagehistoryDao.findAll();
    }

    @Transactional(readOnly = true)
    public MileagehistoryDto findById(Long id) {
        return mileagehistoryDao.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "마일리지 이력을 찾을 수 없습니다."));
    }

    @Transactional
    public MileagehistoryDto create(MileagehistoryDto mileagehistory) {
        validate(mileagehistory);
        mileagehistory.setMileagehistoryid(null);
        mileagehistory.setOffice(resolveOffice(mileagehistory.getOffice().getOffice_id()));
        if (mileagehistory.getCreatedat() == null) {
            mileagehistory.setCreatedat(new java.util.Date());
        }
        return mileagehistoryDao.saveAndFlush(mileagehistory);
    }

    @Transactional
    public MileagehistoryDto update(Long id, MileagehistoryDto request) {
        validate(request);
        MileagehistoryDto current = findById(id);
        current.setMileagetypecode(request.getMileagetypecode());
        current.setAmount(request.getAmount());
        current.setReferencetypecode(request.getReferencetypecode());
        current.setReferenceid(request.getReferenceid());
        current.setDescription(request.getDescription());
        current.setOffice(resolveOffice(request.getOffice().getOffice_id()));
        return mileagehistoryDao.saveAndFlush(current);
    }

    @Transactional
    public void delete(Long id) {
        MileagehistoryDto current = findById(id);
        mileagehistoryDao.delete(current);
    }

    private Office resolveOffice(Long officeId) {
        if (officeId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "office.office_id가 필요합니다.");
        }
        return userRepository.findById(officeId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "해당 office_id의 사무실을 찾을 수 없습니다."));
    }

    private static void validate(MileagehistoryDto mileagehistory) {
        if (mileagehistory == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 본문이 필요합니다.");
        }
        if (mileagehistory.getMileagetypecode() == null || mileagehistory.getMileagetypecode().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "마일리지 유형 코드가 필요합니다.");
        }
        if (mileagehistory.getAmount() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "마일리지 금액이 필요합니다.");
        }
        if (mileagehistory.getOffice() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "소속 사무실이 필요합니다.");
        }
    }
}