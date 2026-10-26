
package kr.co.alpharking.controller.auditlog;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dao.auditlog.AuditlogDao;
import kr.co.alpharking.dto.auditlog.AuditlogDto;

import lombok.RequiredArgsConstructor;

@RestController
@RequestMapping("/api/auditlogs")
@RequiredArgsConstructor
public class AuditlogController {

    private final AuditlogDao auditlogDao;

    // 감사 로그 전체 조회
    @GetMapping
    public List<AuditlogDto> list() {
        return auditlogDao.list();
    }
}
