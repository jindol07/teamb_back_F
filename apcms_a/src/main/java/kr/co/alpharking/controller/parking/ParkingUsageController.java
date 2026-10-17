package kr.co.alpharking.controller.parking;

import java.util.List;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.parking.*;
import kr.co.alpharking.service.parking.ParkingUsageService;

@RestController
@RequestMapping("/api/parking/usages")
public class ParkingUsageController {
    private final ParkingUsageService service;
    public ParkingUsageController(ParkingUsageService service) { this.service = service; }

    private void requireAdmin(HttpSession session) {
        if (!(session.getAttribute("adminId") instanceof Number)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "관리자 로그인이 필요합니다.");
        }
    }

    @GetMapping("/active")
    public List<ParkingUsageRow> active(HttpSession session) {
        requireAdmin(session);
        return service.active();
    }

    @GetMapping
    public List<ParkingUsageRow> recent(HttpSession session) {
        requireAdmin(session);
        return service.recent();
    }

    @PostMapping("/entry")
    public ParkingUsageRow entry(@RequestBody ParkingEntryRequest request, HttpSession session) {
        requireAdmin(session);
        if (request == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 본문이 필요합니다.");
        return service.enter(request.vehicleNumber());
    }

    @PatchMapping("/{id}/exit")
    public ParkingUsageRow exit(@PathVariable Long id, HttpSession session) {
        requireAdmin(session);
        return service.exit(id);
    }

    @PatchMapping("/{id}/space")
    public ParkingUsageRow assign(@PathVariable Long id, @RequestBody ParkingAssignRequest request, HttpSession session) {
        requireAdmin(session);
        if (request == null) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "요청 본문이 필요합니다.");
        return service.assign(id, request.parkingSpaceId());
    }
}
