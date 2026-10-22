
package kr.co.alpharking.dao.auditlog;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;

import kr.co.alpharking.dto.auditlog.AuditlogDto;

@Mapper
public interface AuditlogDao {

    // 감사 로그 등록
    int add(AuditlogDto auditlogDto);

    // 감사 로그 전체 조회
    List<AuditlogDto> list();

}