package kr.co.alpharking.controller.parking;

import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.*;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.service.parking.ParkingUsageService;

@RestController
@RequestMapping("/api/parking/usages")
public class ParkingUsageController {
    private final ParkingUsageService service;
    public ParkingUsageController(ParkingUsageService service) { this.service = service; }

    private void requireAdmin(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
        if (!(authentication.getPrincipal() instanceof Admin admin) || admin.getAdmin_id() == null
                || authentication.getAuthorities().stream().noneMatch(authority -> "ADMIN".equals(authority.getAuthority()))) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
    }

    @GetMapping("/active")
    public List<ParkingUsageRow> active(Authentication authentication) {
        requireAdmin(authentication);
        return service.active();
    }

    @GetMapping
    public List<ParkingUsageRow> recent(Authentication authentication) {
        requireAdmin(authentication);
        return service.recent();
    }

    @PostMapping("/entry")
    public ParkingUsageRow entry(@RequestBody ParkingEntryRequest request, Authentication authentication) {
        requireAdmin(authentication);
        if (request == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 본문이 필요합니다.");
        return service.enter(request.vehicleNumber());
    }

    @PatchMapping("/{id}/exit")
    public ParkingUsageRow exit(@PathVariable Long id, Authentication authentication) {
        requireAdmin(authentication);
        return service.exit(id);
    }

    @PatchMapping("/{id}/space")
    public ParkingUsageRow assign(@PathVariable Long id, @RequestBody ParkingAssignRequest request, Authentication authentication) {
        requireAdmin(authentication);
        if (request == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 본문이 필요합니다.");
        return service.assign(id, request.parkingSpaceId());
    }
}
