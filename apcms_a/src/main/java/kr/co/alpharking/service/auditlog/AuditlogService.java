
package kr.co.alpharking.service.auditlog;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.dao.auditlog.AuditlogDao;
import kr.co.alpharking.dto.auditlog.AuditlogDto;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class AuditlogService {

    private final AuditlogDao auditlogDao;

    // 감사 로그 등록
    @Transactional
    public void add(AuditlogDto auditlogDto) {
        auditlogDao.add(auditlogDto);
    }

    // 감사 로그 전체 조회
    @Transactional(readOnly = true)
    public List<AuditlogDto> list() {
        return auditlogDao.list();
    }
}