package kr.co.alpharking.service.parking;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import org.mockito.ArgumentCaptor;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;
import org.springframework.web.server.ResponseStatusException;
import tools.jackson.databind.json.JsonMapper;
import kr.co.alpharking.controller.parking.ParkingUsageController;
import kr.co.alpharking.dao.parking.AiParkingDecisionDao;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.*;
import kr.co.alpharking.security.Admin;

/** DB·계정 없이 저장 계약, 관리자 경계, 연결·판정의 트랜잭션 실패 처리를 검사합니다. */
class AiParkingDecisionContractTest {
    final AiParkingDecisionDao dao = mock(AiParkingDecisionDao.class);
    final AiParkingDecisionService decisions = new AiParkingDecisionService(dao, JsonMapper.builder().build());
    final Timestamp at = Timestamp.valueOf("2026-10-26 12:00:00");
    AiVehicleEventRequest request() {
        return new AiVehicleEventRequest(UUID.randomUUID().toString(), "VEHICLE_SPACE_MATCH",
            "2026-10-26T12:00:00+09:00", "PARKING_0", null, "91소6408", "1F-A01", BigDecimal.ONE, "TRACKING", 70L);
    }
    AiVehicleEventResponse response(AiVehicleEventRequest r, String code, String outcome) {
        return new AiVehicleEventResponse(r.eventId(),r.eventType(),outcome,r.plateNumber(),r.spaceCode(),70L,"",null,code);
    }

    @Test void fourDecisionsRoundTripWithoutExposingRawPayload() {
        when(dao.insert(eq(16L),eq(at),anyString())).thenReturn(1);
        for (String code : List.of("MATCHED","WRONG_SPACE","NO_VALID_RESERVATION","UNDETERMINED")) {
            var r = request();
            decisions.record(16L,at,r,response(r,code,code.equals("MATCHED") ? "PROCESSED" : "PENDING"));
            var raw = ArgumentCaptor.forClass(String.class);
            verify(dao,atLeastOnce()).insert(eq(16L),eq(at),raw.capture());
            String saved = raw.getValue();
            assertTrue(saved.contains("\"event_type\":\"PARKING_DECISION\""));
            assertFalse(saved.contains("API_KEY"));
            when(dao.recent()).thenReturn(List.of(new AiParkingDecisionDao.Stored(100L,saved)));
            var row = decisions.recent().get(0);
            assertEquals(code,row.parkingDecision());
            assertEquals(r.eventId(),row.eventId());
            assertEquals(100L,row.aiDetectionEventId());
            assertEquals(70L,row.expectedParkingUsageId());
            assertEquals("91소6408",row.plateNumber());
        }
    }
    @Test void missingRegisteredSpaceDoesNotCreateAnEvent() {
        var r=request(); decisions.record(null,at,r,response(r,"UNDETERMINED","PENDING"));
        verifyNoInteractions(dao);
    }
    @Test void globalPrettyPrintingCannotHideStoredDecisionsFromQuery() {
        var pretty = JsonMapper.builder().enable(tools.jackson.databind.SerializationFeature.INDENT_OUTPUT).build();
        var target = new AiParkingDecisionService(dao, pretty);
        when(dao.insert(eq(16L),eq(at),anyString())).thenReturn(1);
        var r=request(); target.record(16L,at,r,response(r,"MATCHED","PROCESSED"));
        var raw=ArgumentCaptor.forClass(String.class);
        verify(dao).insert(eq(16L),eq(at),raw.capture());
        assertTrue(raw.getValue().contains("\"event_type\":\"PARKING_DECISION\""));
        assertFalse(raw.getValue().contains("\n"));
    }
    @Test void failedInsertIsNotReportedAsSuccess() {
        var r=request();
        assertThrows(IllegalStateException.class,() -> decisions.record(16L,at,r,response(r,"MATCHED","PROCESSED")));
    }
    @Test void malformedOrOtherEventTypesAreNotPresentedAsDecisions() {
        for (String raw : List.of("{}", "{\"event_type\":\"PARKING_OCCUPANCY\"}", "not-json")) {
            when(dao.recent()).thenReturn(List.of(new AiParkingDecisionDao.Stored(100L,raw)));
            assertThrows(RuntimeException.class,() -> decisions.recent());
        }
    }
    @Test void contradictoryDecisionIsRejectedBeforeInsert() {
        var r=request();
        assertThrows(IllegalStateException.class,() -> decisions.record(16L,at,r,response(r,"MATCHED","PENDING")));
        verifyNoInteractions(dao);
    }
    @Test void adminEndpointRejectsAnonymousAndNonAdminPrincipals() {
        var controller=new ParkingUsageController(mock(ParkingUsageService.class),decisions);
        assertEquals(401,assertThrows(ResponseStatusException.class,() -> controller.aiDecisions(null)).getStatusCode().value());
        var token = new UsernamePasswordAuthenticationToken("ordinary-user","unused",List.of(new SimpleGrantedAuthority("ADMIN")));
        assertEquals(403,assertThrows(ResponseStatusException.class,() -> controller.aiDecisions(token)).getStatusCode().value());
        verifyNoInteractions(dao);
    }
    @Test void realAdminCanReadAndEmptyResultsRemainEmpty() {
        var admin=new Admin();admin.setAdmin_id(1L);
        var token = new UsernamePasswordAuthenticationToken(admin,"unused",List.of(new SimpleGrantedAuthority("ADMIN")));
        when(dao.recent()).thenReturn(List.of());
        assertEquals(List.of(),new ParkingUsageController(mock(ParkingUsageService.class),decisions).aiDecisions(token));
        verify(dao).recent();
    }

    static class Transactions extends AbstractPlatformTransactionManager {
        int commits,rollbacks;
        protected Object doGetTransaction() { return new Object(); }
        protected void doBegin(Object transaction,TransactionDefinition definition) {}
        protected void doCommit(DefaultTransactionStatus status) { commits++; }
        protected void doRollback(DefaultTransactionStatus status) { rollbacks++; }
    }
    @Test void eventTransactionRollsBackWhenDecisionStorageFails() {
        var usageDao=mock(ParkingUsageDao.class);var usages=mock(ParkingUsageService.class);
        var recorder=mock(AiParkingDecisionService.class);var r=request();
        when(usageDao.findUniqueOpenUsageByPlate(r.plateNumber())).thenReturn(70L);
        when(usageDao.findSpaceIdByCode(r.spaceCode())).thenReturn(16L);
        when(usages.assignReservedForAi(eq(70L),eq(16L),anyString(),any()))
            .thenReturn(new ParkingUsageService.ReservedAssignmentResult(null,null,false));
        doThrow(new IllegalStateException("storage failed")).when(recorder).record(any(),any(),any(),any());
        var tx=new Transactions();
        var proxy=new ProxyFactory(new AiVehicleEventService(usageDao,usages,recorder));
        proxy.addAdvice(new TransactionInterceptor(tx,new AnnotationTransactionAttributeSource()));
        assertThrows(IllegalStateException.class,() -> ((AiVehicleEventService)proxy.getProxy()).receive(r,"VEHICLE_SPACE_MATCH"));
        verify(usages).assignReservedForAi(eq(70L),eq(16L),anyString(),any());
        assertEquals(1,tx.rollbacks);assertEquals(0,tx.commits);
    }
}
