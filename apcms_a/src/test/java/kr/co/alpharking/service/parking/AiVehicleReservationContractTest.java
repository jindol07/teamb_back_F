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
    private final AiVehicleEventService service = new AiVehicleEventService(dao, usage);

    private AiVehicleEventRequest request(String type, String direction, String space) {
        return new AiVehicleEventRequest(UUID.randomUUID().toString(), type,
            "2026-10-22T12:00:00+09:00", "PARKING-1", direction,
            "91소6408", space, new BigDecimal("0.9"), space == null ? null : "TRACKING");
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
        verify(usage).assignReservedForAi(70L, 16L, "91소6408", Timestamp.valueOf("2026-10-22 12:00:00"));
        verify(usage, never()).assignForAi(any(), any());
    }
    @Test void rejectedReservationRemainsPending() {
        prepare(false, "예약 불일치");
        var result = service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH");
        assertEquals("PENDING", result.outcome());
        assertEquals("예약 불일치", result.detail());
    }
    @Test void unchangedIsReturnedOnlyAfterReservationServiceValidation() {
        prepare(true, null);
        assertEquals("UNCHANGED", service.receive(request("VEHICLE_SPACE_MATCH", null, "1F-A01"), "VEHICLE_SPACE_MATCH").outcome());
        verify(usage).assignReservedForAi(eq(70L), eq(16L), eq("91소6408"), any());
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

    private Configuration mapper() throws Exception {
        Configuration config = new Configuration();
        config.getTypeAliasRegistry().registerAlias(kr.co.alpharking.dto.parking.ParkingUsageRow.class);
        try (var stream = getClass().getResourceAsStream("/mapper/parking-usage.xml")) {
            assertNotNull(stream);
            new XMLMapperBuilder(stream, config, "mapper/parking-usage.xml", config.getSqlFragments()).parse();
        }
        return config;
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
