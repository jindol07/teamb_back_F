package kr.co.alpharking.service.parking;

import java.sql.Timestamp;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.SerializationFeature;
import kr.co.alpharking.dao.parking.AiParkingDecisionDao;
import kr.co.alpharking.dto.parking.AiParkingDecisionRow;
import kr.co.alpharking.dto.parking.AiVehicleEventRequest;
import kr.co.alpharking.dto.parking.AiVehicleEventResponse;

@Service
public class AiParkingDecisionService {
    private static final Set<String> DECISIONS = Set.of("MATCHED", "WRONG_SPACE", "NO_VALID_RESERVATION", "UNDETERMINED");
    private final AiParkingDecisionDao dao;
    private final ObjectMapper mapper;
    public AiParkingDecisionService(AiParkingDecisionDao dao, ObjectMapper mapper) {
        this.dao = dao; this.mapper = mapper;
    }

    // 1. 연결 처리와 같은 트랜잭션입니다. 기록 실패 시 연결도 함께 롤백합니다.
    @Transactional(propagation = Propagation.MANDATORY)
    public void record(Long spaceId, Timestamp at, AiVehicleEventRequest request, AiVehicleEventResponse response) {
        if (spaceId == null) return; // 등록되지 않은 구획은 외래키 없는 임의 이력으로 만들지 않습니다.
        var row = new AiParkingDecisionRow(null, response.eventId(), request.detectedAt(), request.cameraId(),
            response.plateNumber(), response.spaceCode(), response.parkingUsageId(),
            request.expectedParkingUsageId(), response.parkingDecision(), response.outcome());
        validate(row);
        // 1-1. 공용 JSON 들여쓰기 설정과 무관하게 DAO가 찾는 유형 표기를 고정합니다.
        String raw = mapper.writer().without(SerializationFeature.INDENT_OUTPUT)
            .writeValueAsString(Map.of("event_type", "PARKING_DECISION", "decision", row));
        if (dao.insert(spaceId, at, raw) != 1) throw new IllegalStateException("주차 판정 기록 저장 실패");
    }

    // 2. 관리자 인증은 Controller에서 검사합니다. 잘못된 저장 자료를 정상 판정으로 바꾸지 않습니다.
    @Transactional(readOnly = true)
    public List<AiParkingDecisionRow> recent() {
        return dao.recent().stream().map(stored -> {
            var root = mapper.readTree(stored.rawPayload());
            if (!"PARKING_DECISION".equals(root.path("event_type").asText()))
                throw new IllegalStateException("주차 판정 기록 유형 오류");
            var row = mapper.treeToValue(root.path("decision"), AiParkingDecisionRow.class);
            validate(row);
            return new AiParkingDecisionRow(stored.id(), row.eventId(), row.detectedAt(), row.cameraId(),
                row.plateNumber(), row.spaceCode(), row.parkingUsageId(), row.expectedParkingUsageId(),
                row.parkingDecision(), row.outcome());
        }).toList();
    }

    private static void validate(AiParkingDecisionRow row) {
        if (row == null || row.parkingDecision() == null || !DECISIONS.contains(row.parkingDecision())
            || !Set.of("PROCESSED", "UNCHANGED", "PENDING").contains(row.outcome())
            || ("MATCHED".equals(row.parkingDecision()) == "PENDING".equals(row.outcome())))
            throw new IllegalStateException("주차 판정 기록 내용 오류");
    }
}
