package kr.co.alpharking.controller.parking;

import java.util.List;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.ParkingSpaceRow;
import kr.co.alpharking.dto.parking.ParkingSpaceUpdateRequest;
import kr.co.alpharking.dto.parking.ParkingSpacePublicRow;
import kr.co.alpharking.service.parking.ParkingSpaceService;

/** 이 브랜치는 조회 전용. 수정/이력/AI 처리는 후속 feature 브랜치에서 구현. */
@RestController
@RequestMapping("/api/parking/spaces")
public class ParkingSpaceController {
    private final ParkingSpaceService service;
    public ParkingSpaceController(ParkingSpaceService service) { this.service = service; }

    /** 관리자 강제 변경: 로그인 세션의 관리자 PK로만 저장한다. */
    @PatchMapping("/{parkingSpaceId}")
    public ParkingSpaceRow updateSpace(@PathVariable Long parkingSpaceId,
                                       @RequestBody ParkingSpaceUpdateRequest request,
                                       HttpSession session) {
        Object adminId = session.getAttribute("adminId");
        if (!(adminId instanceof Number)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        return service.updateSpace(parkingSpaceId, request, ((Number) adminId).longValue());
    }

    /** 공개 화면. 메모/차량번호를 노출하지 않음. */
    @GetMapping("/public")
    public List<ParkingSpacePublicRow> publicSpaces() { return service.findAllPublic(); }

    /** 관리자 화면. 로그인 연동 전에는 의도적으로 401 응답. */
    @GetMapping
    public List<ParkingSpaceRow> adminSpaces(HttpSession session) {
        Object adminId = session.getAttribute("adminId");
        if (!(adminId instanceof Number)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        return service.findAllAdmin();
    }
}
