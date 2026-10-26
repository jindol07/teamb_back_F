package kr.co.alpharking.dao.parking;

import java.sql.Timestamp;
import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** 기존 감지 이벤트의 주차 판정만 저장·조회합니다. Oracle 11g와 21c 공통 SQL입니다. */
@Repository
public class AiParkingDecisionDao {
    private final JdbcTemplate jdbc;
    public AiParkingDecisionDao(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public record Stored(long id, String rawPayload) {}

    // 1. 구획이 실제 존재할 때만 기록하며 구획 상태와 화재 사건은 변경하지 않습니다.
    public int insert(Long spaceId, Timestamp detectedAt, String rawPayload) {
        return jdbc.update("""
            INSERT INTO AI_DETECTION_EVENT
                (AI_DETECTION_EVENT_ID, PARKING_SPACE_ID, DETECTED_AT, CREATED_AT, RAW_PAYLOAD)
            SELECT SEQ_AI_DETECTION_EVENT.NEXTVAL, PARKING_SPACE_ID, ?, SYSDATE, ?
              FROM PARKING_SPACE WHERE PARKING_SPACE_ID = ?
            """, detectedAt, rawPayload, spaceId);
    }

    // 2. 감지 시각과 별개로 최근 저장된 200건을 조회합니다. JSON 전용 SQL은 사용하지 않습니다.
    public List<Stored> recent() {
        return jdbc.query("""
            SELECT AI_DETECTION_EVENT_ID, RAW_PAYLOAD FROM (
                SELECT AI_DETECTION_EVENT_ID, RAW_PAYLOAD FROM AI_DETECTION_EVENT
                 WHERE DBMS_LOB.INSTR(RAW_PAYLOAD, '"event_type":"PARKING_DECISION"') > 0
                 ORDER BY AI_DETECTION_EVENT_ID DESC
            ) WHERE ROWNUM <= 200
            """, (rs, index) -> new Stored(rs.getLong(1), rs.getString(2)));
    }
}
