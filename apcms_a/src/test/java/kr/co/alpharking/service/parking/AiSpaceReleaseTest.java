package kr.co.alpharking.service.parking;

import java.sql.Timestamp;
import java.util.Map;
import java.util.UUID;
import org.apache.ibatis.builder.xml.XMLMapperBuilder;
import org.apache.ibatis.session.Configuration;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.*;
import kr.co.alpharking.controller.parking.AiVehicleEventController;

/** 실제 DB 변경 없이 해제 조건과 조건부 갱신 호출을 검사한다. */
class AiSpaceReleaseTest {
    ParkingUsageDao dao;
    ParkingUsageService usage;
    ParkingUsageRow current, saved;
    final Timestamp at=Timestamp.valueOf("2026-10-23 09:00:00");
    @BeforeEach void setup() {
        dao=mock(ParkingUsageDao.class); usage=new ParkingUsageService(dao);
        current=new ParkingUsageRow(); current.setParkingUsageId(70L); current.setVehicleNumber("91소6408");
        current.setParkingSpaceId(16L); current.setParkingReservationId(90L); current.setEntryAt("2026-10-22T11:00:00");
        saved=new ParkingUsageRow(); saved.setParkingUsageId(70L); saved.setVehicleNumber("91소6408");
        when(dao.lockSpaceStatus(16L)).thenReturn("AVAILABLE"); when(dao.lockOpenUsage(70L)).thenReturn(current);
        when(dao.countActiveByPlate("91소6408")).thenReturn(1); when(dao.lockLinkVersion(70L)).thenReturn(4L,5L);
        when(dao.releaseAiSpace(70L,16L,"91소6408",4L)).thenReturn(1); when(dao.findById(70L)).thenReturn(saved);
    }
    ParkingUsageService.ReleaseResult release() { return usage.releaseForAi(70L,16L,"91소6408",4L,at); }
    void held() { assertNotNull(release().conflictReason()); verify(dao,never()).releaseAiSpace(any(),any(),any(),any()); }
    @Test void clearsBothLinksAndChecksIncrementInLockOrder() {
        var result=release(); assertNull(result.conflictReason()); assertEquals(5L,result.linkVersion());
        var order=inOrder(dao); order.verify(dao).lockSpaceStatus(16L); order.verify(dao).lockOpenUsage(70L);
        order.verify(dao).lockLinkVersion(70L); order.verify(dao).releaseAiSpace(70L,16L,"91소6408",4L);
        verify(dao,never()).exitUsage(any(),any()); verify(dao,never()).detachSpace(any(),any());
    }
    @Test void occupiedIsHeld() { when(dao.lockSpaceStatus(16L)).thenReturn("OCCUPIED"); held(); }
    @Test void protectedIsHeld() { when(dao.lockSpaceStatus(16L)).thenReturn("DISABLED"); held(); }
    @Test void closedUsageIsHeld() { when(dao.lockOpenUsage(70L)).thenReturn(null); held(); }
    @Test void anotherPlateIsHeld() { current.setVehicleNumber("12가3456"); held(); }
    @Test void anotherSpaceIsHeld() { current.setParkingSpaceId(17L); held(); }
    @Test void duplicateUsageIsHeld() { when(dao.countActiveByPlate("91소6408")).thenReturn(2); held(); }
    @Test void olderGenerationAfterReturnToSameSpaceIsHeld() { when(dao.lockLinkVersion(70L)).thenReturn(6L); held(); }
    @Test void unknownVersionIsHeld() { when(dao.lockLinkVersion(70L)).thenReturn((Long)null); held(); }
    @Test void beforeEntryIsHeld() { current.setEntryAt("2026-10-23T09:01:00"); held(); }
    @Test void priorAdminCorrectionIsHeld() { when(dao.latestAdminChangedAt(16L)).thenReturn(at); held(); }
    @Test void zeroUpdatedIsPending() { when(dao.releaseAiSpace(70L,16L,"91소6408",4L)).thenReturn(0); assertNotNull(release().conflictReason()); }
    @Test void multipleUpdatedThrowsForRollback() { when(dao.releaseAiSpace(70L,16L,"91소6408",4L)).thenReturn(2); assertThrows(IllegalStateException.class,this::release); }
    @Test void missingTriggerIncrementThrowsForRollback() { when(dao.lockLinkVersion(70L)).thenReturn(4L); assertThrows(IllegalStateException.class,this::release); }
    @Test void remainingReservationThrowsForRollback() { saved.setParkingReservationId(90L); assertThrows(IllegalStateException.class,this::release); }
    @Test void unexpectedExitThrowsForRollback() { saved.setExitAt("2026-10-23T09:00:00"); assertThrows(IllegalStateException.class,this::release); }
    @Test void repeatedReleaseIsHeld() { current.setParkingSpaceId(null); held(); }
    @Test void invalidVersionNeverTouchesDao() {
        clearInvocations(dao); assertThrows(ResponseStatusException.class,()->usage.releaseForAi(70L,16L,"91소6408",-1L,at)); verifyNoInteractions(dao);
    }
    AiSpaceReleaseRequest request(Long version,String reason) {
        return new AiSpaceReleaseRequest(UUID.randomUUID().toString(),"VEHICLE_SPACE_RELEASE",
            "2026-10-22T12:00:00+09:00","PARKING_1","91소6408","1F-A01",70L,version,reason);
    }
    AiVehicleEventService events(ParkingUsageService target,boolean enabled) {
        var events=new AiVehicleEventService(dao,target); ReflectionTestUtils.setField(events,"spaceReleaseEnabled",enabled); return events;
    }
    @Test void defaultDisabledDoesNotQueryNewColumn() {
        var target=mock(ParkingUsageService.class); var events=new AiVehicleEventService(dao,target); clearInvocations(dao);
        var error=assertThrows(ResponseStatusException.class,()->events.release(request(4L,"CONFIRMED_EMPTY")));
        assertEquals(503,error.getStatusCode().value()); verifyNoInteractions(dao,target);
    }
    @Test void validReleaseReturnsConfirmedGeneration() {
        var target=mock(ParkingUsageService.class); when(dao.findSpaceIdByCode("1F-A01")).thenReturn(16L);
        when(target.releaseForAi(eq(70L),eq(16L),eq("91소6408"),eq(4L),any())).thenReturn(new ParkingUsageService.ReleaseResult(saved,null,5L));
        var result=events(target,true).release(request(4L,"CONFIRMED_EMPTY")); assertEquals("PROCESSED",result.outcome()); assertEquals(5L,result.linkVersion());
    }
    @Test void trackingLossIsNotReleaseEvidence() {
        var target=mock(ParkingUsageService.class); assertThrows(ResponseStatusException.class,()->events(target,true).release(request(4L,"TRACK_LOST"))); verifyNoInteractions(target);
    }
    @Test void missingVersionIsRejected() { assertThrows(ResponseStatusException.class,()->events(mock(ParkingUsageService.class),true).release(request(null,"CONFIRMED_EMPTY"))); }
    @Test void releaseRouteRequiresSameApiKey() {
        var target=mock(AiVehicleEventService.class); var controller=new AiVehicleEventController(target,"KEY");
        assertThrows(ResponseStatusException.class,()->controller.release("WRONG",request(4L,"CONFIRMED_EMPTY"))); verifyNoInteractions(target);
        controller.release("KEY",request(4L,"CONFIRMED_EMPTY")); verify(target).release(any());
    }
    @Test void releaseSqlBindsOriginalIdentityAndGeneration() throws Exception {
        var config=new Configuration();
        config.getTypeAliasRegistry().registerAlias(kr.co.alpharking.dto.parking.ParkingUsageRow.class);
        try(var stream=getClass().getResourceAsStream("/mapper/parking-usage.xml")) {
            new XMLMapperBuilder(stream,config,"mapper/parking-usage.xml",config.getSqlFragments()).parse();
        }
        String sql=config.getMappedStatement(ParkingUsageDao.class.getName()+".releaseAiSpace")
            .getBoundSql(Map.of("usageId",70L,"spaceId",16L,"number","91소6408","linkVersion",4L)).getSql().replaceAll("\\s+"," ").toUpperCase();
        assertTrue(sql.contains("PARKING_SPACE_ID = NULL, PARKING_RESERVATION_ID = NULL"));
        assertTrue(sql.contains("PARKING_USAGE_ID = ? AND PARKING_SPACE_ID = ?"));
        assertTrue(sql.contains("VEHICLE_NUMBER = ? AND EXIT_AT IS NULL AND LINK_VERSION = ?"));
        assertFalse(sql.contains("SET EXIT_AT"));
    }
    @Test void enabledMatchReturnsVersionButDefaultAvoidsNewColumn() {
        var target=mock(ParkingUsageService.class);
        when(dao.findUniqueOpenUsageByPlate("91소6408")).thenReturn(70L);
        when(dao.findSpaceIdByCode("1F-A01")).thenReturn(16L);
        when(target.assignReservedForAi(eq(70L),eq(16L),eq("91소6408"),any()))
            .thenReturn(new ParkingUsageService.ReservedAssignmentResult(current,null,true));
        var req=new AiVehicleEventRequest(UUID.randomUUID().toString(),"VEHICLE_SPACE_MATCH",
            "2026-10-22T12:00:00+09:00","PARKING_1",null,"91소6408","1F-A01",new java.math.BigDecimal("0.9"),"TRACKING");
        clearInvocations(dao);
        assertNull(events(target,false).receive(req,"VEHICLE_SPACE_MATCH").linkVersion());
        verify(dao,never()).lockLinkVersion(any());
        assertEquals(4L,events(target,true).receive(req,"VEHICLE_SPACE_MATCH").linkVersion());
    }
    @Test void controllerJsonUsesDedicatedReleaseFieldsAndReturnsVersion() throws Exception {
        var target=mock(ParkingUsageService.class);
        when(dao.findSpaceIdByCode("1F-A01")).thenReturn(16L);
        when(target.releaseForAi(eq(70L),eq(16L),eq("91소6408"),eq(4L),any()))
            .thenReturn(new ParkingUsageService.ReleaseResult(saved,null,5L));
        var controller=new AiVehicleEventController(events(target,true),"KEY");
        var mvc=org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup(controller).build();
        String body="""
            {"event_id":"02f56fb0-cb4f-4fb0-867a-6c31b7b88da3","event_type":"VEHICLE_SPACE_RELEASE",
             "detected_at":"2026-10-22T12:00:00+09:00","camera_id":"PARKING_1","plate_number":"91소6408",
             "space_code":"1F-A01","parking_usage_id":70,"link_version":4,"reason":"CONFIRMED_EMPTY"}
            """;
        var result=mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post("/api/parking/ai/space-release-events")
            .header("X-AI-API-Key","KEY").contentType("application/json").content(body)).andReturn();
        assertEquals(200,result.getResponse().getStatus());
        assertTrue(result.getResponse().getContentAsString().contains("\"linkVersion\":5"));
        assertTrue(result.getResponse().getContentAsString().contains("\"outcome\":\"PROCESSED\""));
    }

    @Test void releaseTimeValidationUsesActualInstantAcrossJvmTimeZones() {
        var original = java.util.TimeZone.getDefault();
        try {
            for (String zone : new String[]{"UTC", "Asia/Seoul"}) {
                java.util.TimeZone.setDefault(java.util.TimeZone.getTimeZone(zone));
                var service = new AiVehicleEventService(dao, usage);
                ReflectionTestUtils.setField(service, "spaceReleaseEnabled", true);
                var now = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC);
                var valid = new AiSpaceReleaseRequest(UUID.randomUUID().toString(), "VEHICLE_SPACE_RELEASE",
                    now.minusSeconds(5).toString(), "PARKING_1", "91소6408", "1F-A01", 70L, 4L, "CONFIRMED_EMPTY");
                assertEquals("PENDING", service.release(valid).outcome(), zone);
                var future = new AiSpaceReleaseRequest(UUID.randomUUID().toString(), "VEHICLE_SPACE_RELEASE",
                    now.plusSeconds(120).toString(), "PARKING_1", "91소6408", "1F-A01", 70L, 4L, "CONFIRMED_EMPTY");
                var error = assertThrows(ResponseStatusException.class, () -> service.release(future), zone);
                assertEquals(400, error.getStatusCode().value());
            }
        } finally {
            java.util.TimeZone.setDefault(original);
        }
    }
}
