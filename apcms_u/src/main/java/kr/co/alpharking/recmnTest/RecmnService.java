package kr.co.alpharking.recmnTest;

import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class RecmnService {

    @Autowired
    private RecmnRepository recmnRepository;

    public List<PrkPastHisRes> getPrkPastHisById(Long officeId) {

        // 1. Repository에서 과거 주차이력 조회
        List<Object[]> rows = recmnRepository.getPrkPastHisById(officeId);

        // 2. 반환할 DTO 리스트 생성
        List<PrkPastHisRes> result = new ArrayList<>();

        // 3. 조회된 주차이력을 한 건씩 DTO로 변환
        for (Object[] row : rows) {

            PrkPastHisRes dto = new PrkPastHisRes();

            // Oracle NUMBER 타입은 Number로 받아 Integer로 변환
            dto.setUsageId(((Number) row[0]).intValue());
            dto.setOfficeId(((Number) row[1]).intValue());

            // TO_CHAR 결과는 문자열로 변환
            dto.setUsageDate((String) row[2]);
            dto.setTargetZone((String) row[3]);

            // 4. DTO 리스트에 추가
            result.add(dto);
        }

        // 5. 변환된 주차이력 리스트 반환
        return result;
    }
}