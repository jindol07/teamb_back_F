package kr.co.alpharking.controller.parking;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
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
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.parking.ParkingSpaceService;

/** 주차구획 조회 및 JWT로 인증된 관리자의 구획 변경. */
@RestController
@RequestMapping("/api/parking/spaces")
public class ParkingSpaceController {
    private final ParkingSpaceService service;
    public ParkingSpaceController(ParkingSpaceService service) { this.service = service; }

    private Admin requireAdmin(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        if (!(authentication.getPrincipal() instanceof Admin admin) || admin.getAdmin_id() == null
                || authentication.getAuthorities().stream().noneMatch(authority -> "ADMIN".equals(authority.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
        return admin;
    }

    /** 관리자 강제 변경: JWT로 인증된 관리자의 PK로 이력을 저장한다. */
    @PatchMapping("/{parkingSpaceId}")
    public ParkingSpaceRow updateSpace(@PathVariable Long parkingSpaceId,
                                       @RequestBody ParkingSpaceUpdateRequest request,
                                       Authentication authentication) {
        Admin admin = requireAdmin(authentication);
        return service.updateSpace(parkingSpaceId, request, admin.getAdmin_id());
    }

    /** 로그인 사용자용 현황. 메모/차량번호를 노출하지 않음. */
    @GetMapping("/public")
    public List<ParkingSpacePublicRow> publicSpaces() { return service.findAllPublic(); }

    /** 관리자 화면. JWT 인증 및 관리자 권한이 필요하다. */
    @GetMapping
    public List<ParkingSpaceRow> adminSpaces(Authentication authentication) {
        requireAdmin(authentication);
        return service.findAllAdmin();
    }
}
