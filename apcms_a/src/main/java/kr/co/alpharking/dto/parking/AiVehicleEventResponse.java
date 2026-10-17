package kr.co.alpharking.dto.parking;

public record AiVehicleEventResponse(String eventId, String eventType, String outcome,
                                     String plateNumber, String spaceCode,
                                     Long parkingUsageId, String detail) {}
