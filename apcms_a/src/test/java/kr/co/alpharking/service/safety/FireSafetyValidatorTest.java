package kr.co.alpharking.service.safety;

import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import kr.co.alpharking.dto.safety.FireSafetyRequest;
import static org.junit.jupiter.api.Assertions.*;

class FireSafetyValidatorTest {
    static final String ID="a".repeat(64);
    private FireSafetyRequest sample(String state, BigDecimal conf) {
        return new FireSafetyRequest("1.0",ID,"event-1","region-1","FIRE",state,
           "2026-10-22T03:00:00+00:00",BigDecimal.ONE,10L,conf,
           List.of(1,2,30,40),3L,null,new FireSafetyRequest.Source("CAMERA","camera_0"),
           "2026-10-22T02:00:00+00:00",true,true);
    }
    @Test void validFire() { assertDoesNotThrow(()->FireSafetyValidator.validate(sample("SUSPECTED",new BigDecimal("0.875")),ID)); }
    @Test void validCleared() { assertDoesNotThrow(()->FireSafetyValidator.validate(sample("CLEARED",new BigDecimal("0.7")),ID)); }
    @Test void rejectsBadKey() { assertThrows(ResponseStatusException.class,()->FireSafetyValidator.validate(sample("SUSPECTED",BigDecimal.ONE),"b".repeat(64))); }
    @Test void rejectsConfidenceOverflow() { assertThrows(ResponseStatusException.class,()->FireSafetyValidator.validate(sample("SUSPECTED",new BigDecimal("1.001")),ID)); }
    @Test void rejectsUnsupportedState() { assertThrows(ResponseStatusException.class,()->FireSafetyValidator.validate(sample("RESOLVED",BigDecimal.ONE),ID)); }
    @Test void correlationStableWithinIncident() {
        var a=sample("SUSPECTED",BigDecimal.ONE);
        var b=sample("REOPENED",new BigDecimal("0.3"));
        assertEquals(FireSafetyAtomicWriter.correlation(a),FireSafetyAtomicWriter.correlation(b));
    }
}
