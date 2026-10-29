package kr.co.alpharking.service.parking;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.util.Map;
import java.util.UUID;
import org.apache.ibatis.builder.xml.XMLMapperBuilder;
import org.apache.ibatis.session.Configuration;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import kr.co.alpharking.dao.parking.ParkingUsageDao;
import kr.co.alpharking.dto.parking.AiVehicleEventRequest;

class AiVehicleReservationContractTest {
    private final ParkingUsageDao dao = mock(ParkingUsageDao.class);
    private final ParkingUsageService usage = mock(ParkingUsageService.class);
    private final org.springframework.context.ApplicationEventPublisher events = mock(org.springframework.context.ApplicationEventPublisher.class);
    private final AiVehicleEventService service = new AiVehicleEventService(dao, usage, mock(AiParkingDecisionService.class), events);

    private AiVehicleEventRequest request(String type, String direction, String space) {
        return new AiVehicleEventRequest(UUID.randomUUID().toString(), type,
            "2026-10-22T12:00:00+09:00", "PARKING-1", direction,
            "91소6408", space, new BigDecimal("0.9"), space == null ? null : "TRACKING", space == null ? null : 70L);
    }

    private AiVehicleEventRequest withExpected(Long id) {
        var r = request("VEHICLE_SPACE_MATCH", null, "1F-A01");
        return new AiVehicleEventRequest(r.eventId(),r.eventType(),r.detectedAt(),r.cameraId(),
            r.direction(),r.plateNumber(),r.spaceCode(),r.confidence(),r.method(),id);
    }

    @Test void staleOrMissingExpectedUsageNeverCallsAssignment() {
        prepare(false, null);
        for (Long expected : java.util.Arrays.asList(null, 69L, 71L)) {
            var response = service.receive(withExpected(expected), "VEHICLE_SPACE_MATCH");
            assertEquals("PENDING", response.outcome());
            assertEquals("UNDETERMINED", response.parkingDecision());
        }
        verifyNoInteractions(usage);
    }

    @Test void invalidExpectedUsageIsRejectedBeforeLookup() {
        for (long id : new long[]{0L,-1L}) {
            assertThrows(org.springframework.web.server.ResponseStatusException.class,
                () -> service.receive(withExpected(id), "VEHICLE_SPACE_MATCH"));
        }
        verifyNoInteractions(dao, usage);
    }

    private void prepare(boolean unchanged, String reason) {
        when(dao.findUniqueOpenUsageByPlate("91소6408")).thenReturn(70L);
        when(dao.findSpaceIdByCode("1F-A01")).thenReturn(16L);
        when(usage.assignReservedForAi(eq(70L), eq(16L), eq("91소6408"), any()))
            .thenReturn(new ParkingUsageService.ReservedAssignmentResult(null, reason, unchanged));
    }

    @Test void matchCallsReservedAssignmentWithKoreanEventTime() {
        prepare(false, null);
        var result = service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH");
        assertEquals("PROCESSED", result.outcome());
        assertEquals("MATCHED", result.parkingDecision());
        verify(events).publishEvent(any(kr.co.alpharking.websocket.parking.ParkingSpaceChangedEvent.class));
        verify(usage).assignReservedForAi(70L, 16L, "91소6408", Timestamp.valueOf("2026-10-22 12:00:00"));
        verify(usage, never()).assignForAi(any(), any());
    }
    @Test void rejectedReservationRemainsPending() {
        prepare(false, "예약 불일치");
        var result = service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH");
        assertEquals("PENDING", result.outcome());
        assertEquals("예약 불일치", result.detail());
        verifyNoInteractions(events);
    }
    @Test void unchangedIsReturnedOnlyAfterReservationServiceValidation() {
        prepare(true, null);
        assertEquals("UNCHANGED", service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH").outcome());
        verify(usage).assignReservedForAi(eq(70L), eq(16L), eq("91소6408"), any());
        verifyNoInteractions(events);
    }
    @Test void noActiveUsageDoesNotAssign() {
        when(dao.findUniqueOpenUsageByPlate("91소6408")).thenReturn(null);
        when(dao.findSpaceIdByCode("1F-A01")).thenReturn(16L);
        assertEquals("PENDING", service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH").outcome());
        verifyNoInteractions(usage);
    }
    @Test void missingOrDuplicateUsageUsesUniqueLookupOnly() {
        when(dao.findUniqueOpenUsageByPlate("91소6408")).thenReturn(null);
        assertEquals("PENDING", service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH").outcome());
        verify(dao).findUniqueOpenUsageByPlate("91소6408");
        verify(dao, never()).findOpenUsageByPlate(any());
        verifyNoInteractions(usage);
    }
    @Test void existingEntryPassageRemainsUnchangedWithoutReservationLookup() {
        when(dao.findOpenUsageByPlate("91소6408")).thenReturn(70L);
        assertEquals("UNCHANGED", service.receive(request("VEHICLE_PASSAGE", "ENTRY", null), "VEHICLE_PASSAGE").outcome());
        verifyNoInteractions(usage);
    }

    @Test void parkingDecisionDistinguishesReservationOutcomesWithoutWriting() {
        for (String decision : java.util.List.of("WRONG_SPACE", "NO_VALID_RESERVATION", "UNDETERMINED")) {
            prepare(false, "연결 보류");
            when(usage.assignReservedForAi(eq(70L), eq(16L), eq("91소6408"), any()))
                .thenReturn(new ParkingUsageService.ReservedAssignmentResult(null, "연결 보류", false, decision));
            var response = service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH");
            assertEquals("PENDING", response.outcome());
            assertEquals(decision, response.parkingDecision());
        }
    }

    @Test void realServiceClassifiesOwnReservationSeparatelyFromOtherVehicles() {
        var mockDao = mock(ParkingUsageDao.class);
        var real = new ParkingUsageService(mockDao);
        var current = new kr.co.alpharking.dto.parking.ParkingUsageRow();
        current.setVehicleNumber("91소6408"); current.setEntryAt("2026-10-22T11:00:00");
        var at = Timestamp.valueOf("2026-10-22 12:00:00");
        when(mockDao.lockSpaceStatus(16L)).thenReturn("OCCUPIED");
        when(mockDao.lockOpenUsage(70L)).thenReturn(current);
        when(mockDao.countActiveByPlate("91소6408")).thenReturn(1);
        var own = new kr.co.alpharking.dto.parking.ParkingReservationRow();
        own.setParkingReservationId(90L); own.setParkingSpaceId(17L);
        own.setVehicleNumber("91소6408"); own.setStatusCode("CONFIRMED");
        var other = new kr.co.alpharking.dto.parking.ParkingReservationRow();
        other.setParkingReservationId(91L); other.setParkingSpaceId(16L);
        other.setVehicleNumber("12가3456"); other.setStatusCode("CONFIRMED");
        when(mockDao.lockReservationCandidates("91소6408",16L,at)).thenReturn(java.util.List.of(own,other));
        when(mockDao.assignObservedSpace(70L,16L,"91소6408",at)).thenReturn(1);
        var observed = new kr.co.alpharking.dto.parking.ParkingUsageRow();
        observed.setParkingUsageId(70L); observed.setVehicleNumber("91소6408"); observed.setParkingSpaceId(16L);
        when(mockDao.findById(70L)).thenReturn(observed);
        assertEquals("WRONG_SPACE",real.assignReservedForAi(70L,16L,"91소6408",at).parkingDecision());
        when(mockDao.lockReservationCandidates("91소6408",16L,at)).thenReturn(java.util.List.of(other));
        assertEquals("NO_VALID_RESERVATION",real.assignReservedForAi(70L,16L,"91소6408",at).parkingDecision());
        when(mockDao.lockReservationCandidates("91소6408",16L,at)).thenReturn(java.util.List.of(own,own));
        assertEquals("UNDETERMINED",real.assignReservedForAi(70L,16L,"91소6408",at).parkingDecision());
        verify(mockDao,never()).assignReservedSpace(any(),any(),any(),any(),any());
        own.setParkingSpaceId(16L);
        when(mockDao.lockReservationCandidates("91소6408",16L,at)).thenReturn(java.util.List.of(own));
        when(mockDao.assignReservedSpace(70L,16L,90L,"91소6408",at)).thenReturn(1);
        var saved = new kr.co.alpharking.dto.parking.ParkingUsageRow();
        saved.setParkingSpaceId(16L); saved.setParkingReservationId(90L);
        when(mockDao.findById(70L)).thenReturn(saved);
        assertEquals("MATCHED",real.assignReservedForAi(70L,16L,"91소6408",at).parkingDecision());
    }

    private Configuration mapper() throws Exception {
        Configuration config = new Configuration();
        config.getTypeAliasRegistry().registerAlias(kr.co.alpharking.dto.parking.ParkingUsageRow.class);
        try (var stream = getClass().getResourceAsStream("/mapper/parking-usage.xml")) {
            assertNotNull(stream);
            new XMLMapperBuilder(stream, config, "mapper/parking-usage.xml", config.getSqlFragments()).parse();
        }
        return config;
    }

    @Test void observedConnectionReportsSuccessWithoutClaimingReservationMatch() {
        for (String decision : java.util.List.of("NO_VALID_RESERVATION", "WRONG_SPACE")) {
            clearInvocations(events);
            prepare(false, null);
            when(usage.assignReservedForAi(eq(70L), eq(16L), eq("91소6408"), any()))
                .thenReturn(new ParkingUsageService.ReservedAssignmentResult(null, null, false, decision));
            var result = service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH");
            assertEquals("PROCESSED", result.outcome());
            assertEquals(decision, result.parkingDecision());
            assertTrue(result.detail().contains("실제 주차 위치 연결 완료"));
            verify(events).publishEvent(any(kr.co.alpharking.websocket.parking.ParkingSpaceChangedEvent.class));
        }
    }

    @Test void observedSqlGuardsExistingLinksAndActiveUsageWithoutChangingReservations() throws Exception {
        var bound = mapper().getMappedStatement(ParkingUsageDao.class.getName() + ".assignObservedSpace")
            .getBoundSql(Map.of("usageId",70L,"spaceId",16L,"number","91소6408","eventTime",Timestamp.valueOf("2026-10-22 12:00:00")));
        String sql = bound.getSql().replaceAll("\\s+", " ").toUpperCase();
        assertTrue(sql.contains("SET PARKING_SPACE_ID = ?"));
        assertTrue(sql.contains("U.PARKING_RESERVATION_ID IS NULL"));
        assertTrue(sql.contains("U.VEHICLE_NUMBER = ? AND U.ENTRY_AT <= ?"));
        assertTrue(sql.contains("NOT EXISTS"));
        assertFalse(sql.contains("PARKING_RESERVATION_ID ="));
        assertFalse(sql.contains("UPDATE PARKING_RESERVATION"));
    }

    @Test void reservationQueryUsesBothVehicleAndSpaceAndLocksRows() throws Exception {
        String sql = mapper().getMappedStatement(ParkingUsageDao.class.getName() + ".lockReservationCandidates")
            .getBoundSql(Map.of("number", "91소6408", "spaceId", 16L,
                               "eventTime", Timestamp.valueOf("2026-10-22 12:00:00")))
            .getSql().replaceAll("\\s+", " ").toUpperCase();
        assertTrue(sql.contains("STATUS_CODE = 'CONFIRMED' AND CANCELLED_AT IS NULL"));
        assertTrue(sql.contains("RESERVATION_START_AT <= ? AND RESERVATION_END_AT >= ?"));
        assertTrue(sql.contains("VEHICLE_NUMBER = ? OR PARKING_SPACE_ID = ?"));
        assertTrue(sql.contains("ORDER BY PARKING_RESERVATION_ID FOR UPDATE"));
    }

    @Test void uniqueUsageQueryReturnsIdOnlyForSingleOpenUsage() throws Exception {
        String sql = mapper().getMappedStatement(ParkingUsageDao.class.getName() + ".findUniqueOpenUsageByPlate")
            .getBoundSql(Map.of("number", "91소6408")).getSql().replaceAll("\\s+", " ").toUpperCase();
        assertTrue(sql.contains("CASE WHEN COUNT(*) = 1 THEN MAX(PARKING_USAGE_ID) ELSE NULL END"));
        assertTrue(sql.contains("EXIT_AT IS NULL"));
    }

    @Test void updateBindsBothIdsAndRechecksReservationAtWrite() throws Exception {
        var statement = mapper().getMappedStatement(ParkingUsageDao.class.getName() + ".assignReservedSpace");
        var bound = statement.getBoundSql(Map.of("usageId", 70L, "spaceId", 16L, "reservationId", 90L,
            "number", "91소6408", "eventTime", Timestamp.valueOf("2026-10-22 12:00:00")));
        String sql = bound.getSql().replaceAll("\\s+", " ").toUpperCase();
        assertTrue(sql.contains("SET PARKING_SPACE_ID = ?, PARKING_RESERVATION_ID = ?"));
        assertTrue(sql.contains("EXIT_AT IS NULL"));
        assertTrue(sql.contains("AND EXISTS"));
        assertTrue(sql.contains("AND 1 = (SELECT COUNT(*)"));
        var properties = bound.getParameterMappings().stream().map(p -> p.getProperty()).toList();
        assertTrue(properties.containsAll(java.util.List.of("usageId", "spaceId", "reservationId", "number", "eventTime")));
    }

    private String sql(String id) throws Exception {
        return mapper().getMappedStatement(ParkingUsageDao.class.getName() + "." + id)
            .getBoundSql(Map.of("usageId", 70L, "spaceId", 16L, "eventTime", Timestamp.valueOf("2026-10-22 12:00:00")))
            .getSql().replaceAll("\\s+", " ").toUpperCase();
    }

    @Test void detachClearsBothLinksAndKeepsUsageAndOldSpaceConditions() throws Exception {
        String sql = sql("detachSpace");
        assertTrue(sql.contains("SET PARKING_SPACE_ID = NULL, PARKING_RESERVATION_ID = NULL"));
        assertTrue(sql.contains("WHERE PARKING_USAGE_ID = ? AND PARKING_SPACE_ID = ? AND EXIT_AT IS NULL"));
        assertFalse(sql.contains("EXIT_AT ="));
    }

    @Test void manualAssignmentPreservesReservationOnlyForSameExistingSpace() throws Exception {
        String sql = sql("assignSpace");
        assertTrue(sql.contains("PARKING_RESERVATION_ID = CASE WHEN PARKING_SPACE_ID = ? THEN PARKING_RESERVATION_ID ELSE NULL END"));
        assertTrue(sql.contains("PARKING_SPACE_ID = ?"));
        assertTrue(sql.contains("WHERE PARKING_USAGE_ID = ? AND EXIT_AT IS NULL"));
    }

    @Test void exitPreservesHistoricalLinksAndCorrectionReadsReservation() throws Exception {
        String exit = sql("exitUsage");
        assertTrue(exit.contains("SET EXIT_AT = ?"));
        assertFalse(exit.contains("PARKING_RESERVATION_ID ="));
        assertFalse(exit.contains("PARKING_SPACE_ID ="));
        assertTrue(sql("lockActiveOnSpace").contains("PARKING_RESERVATION_ID AS \"PARKINGRESERVATIONID\""));
    }
}
