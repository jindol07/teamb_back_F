package kr.co.alpharking.service.safety;

import kr.co.alpharking.dao.safety.FireSafetyDao;
import kr.co.alpharking.dto.safety.FireSafetyRequest;
import kr.co.alpharking.dto.safety.FireSafetyResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.ObjectMapper;

/** UNIQUE 충돌은 @Transactional Writer 밖에서 처리해 Oracle rollback 상태에서 조회하지 않습니다. */
@Service
public class FireSafetyIngest {
    private final FireSafetyDao dao;
    private final FireSafetyAtomicWriter writer;
    private final ObjectMapper mapper;
    private final boolean allowTest;

    public FireSafetyIngest(FireSafetyDao dao, FireSafetyAtomicWriter writer, ObjectMapper mapper,
            @Value("${fire.alert.allow-test:false}") boolean allowTest) {
        this.dao = dao; this.writer = writer; this.mapper = mapper; this.allowTest = allowTest;
    }

    public FireSafetyResponse receive(FireSafetyRequest request, String idempotencyHeader) {
        FireSafetyValidator.validate(request, idempotencyHeader);
        if (request.isTest() && !allowTest)
            throw new ResponseStatusException(HttpStatus.FORBIDDEN,
                "시험 데이터 수신은 FIRE_ALERT_ALLOW_TEST=true로 명시적으로 허용해야 합니다.");
        String hash = FireSafetyAtomicWriter.requestHash(request, mapper);
        var existing = dao.existing(request.transitionId());
        if (existing != null) return duplicate(request, hash, existing, dao);
        try { return writer.write(request, hash); }
        catch (DuplicateKeyException first) {
            existing = dao.existing(request.transitionId());
            if (existing != null) return duplicate(request, hash, existing, dao);
            // 같은 SOURCE_GROUP_HASH로 동시 신규 사건을 생성한 요청이라면, 선행 커밋 뒤 재시도.
            try { return writer.write(request, hash); }
            catch (DuplicateKeyException second) {
                existing = dao.existing(request.transitionId());
                if (existing != null) return duplicate(request, hash, existing, dao);
                throw second;
            }
        }
    }

    public static FireSafetyResponse duplicate(FireSafetyRequest r, String hash,
                                               FireSafetyDao.Stored old, FireSafetyDao dao) {
        String marker = "\"request_hash\":\"" + hash + "\"";
        if (old.rawPayload() == null || !old.rawPayload().contains(marker))
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                "동일한 전이 ID를 다른 본문에 재사용했습니다.");
        Long incidentId = dao.latestGroupId(FireSafetyAtomicWriter.correlation(r));
        return new FireSafetyResponse(r.transitionId(), "DUPLICATE", old.eventId(),
                incidentId, 0, r.isTest());
    }
}
