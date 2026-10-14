package kr.co.alpharking.service.parking;

import java.util.List;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.ParkingSpaceUpdateRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import kr.co.alpharking.dao.parking.ParkingSpaceDao;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;

@Service
public class ParkingSpaceService {
    private final ParkingSpaceDao dao;
    public ParkingSpaceService(ParkingSpaceDao dao) { this.dao = dao; }

    @Transactional(readOnly = true)
    public List<ParkingSpaceRow> findAllAdmin() { return dao.findAllAdmin(); }

    @Transactional(readOnly = true)
    public List<ParkingSpacePublicRow> findAllPublic() { return dao.findAllPublic(); }

    private static final Set<String> ALLOWED_STATUSES = Set.of("AVAILABLE", "OCCUPIED", "RESERVED", "DISABLED");
    private static final Set<String> ALLOWED_TYPES = Set.of("NORMAL", "ELECTRIC", "DISABLED", "DISABLED_PERSON");

    /** 화면의 저장 버튼에서 호출: 변경과 이력 기록을 하나의 트랜잭션으로 처리. */
    @Transactional
    public ParkingSpaceRow updateSpace(Long id, ParkingSpaceUpdateRequest request, Long adminId) {
        if (request == null || id == null || adminId == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "잘못된 요청입니다.");
        }
        String status = request.spaceStatusCode() == null ? "" : request.spaceStatusCode().trim().toUpperCase();
        String type = request.spaceTypeCode() == null ? "" : request.spaceTypeCode().trim().toUpperCase();
        String memo = request.memo() == null ? "" : request.memo().trim();
        String reason = request.changeReason() == null ? "" : request.changeReason().trim();
        if (!ALLOWED_STATUSES.contains(status) || !ALLOWED_TYPES.contains(type)
                || reason.isBlank() || reason.length() > 500 || memo.length() > 500) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "상태/종류/메모/변경 사유를 확인하세요.");
        }
        ParkingSpaceRow previous = dao.lockForUpdate(id);
        if (previous == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "주차구획이 존재하지 않습니다.");
        if (status.equals(previous.getSpaceStatusCode()) && type.equals(previous.getSpaceTypeCode())
                && memo.equals(previous.getMemo() == null ? "" : previous.getMemo())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "변경된 내용이 없습니다.");
        }
        if (dao.updateAdminSpace(id, status, type, memo) != 1) {
            throw new IllegalStateException("구획 수정 실패");
        }
        dao.closeOpenHistory(id);
        if (dao.insertAdminHistory(id, adminId, reason) != 1) {
            throw new IllegalStateException("구획 변경 이력 저장 실패");
        }
        return dao.findById(id);
    }
}
