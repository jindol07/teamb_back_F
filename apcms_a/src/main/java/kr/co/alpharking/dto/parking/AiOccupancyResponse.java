package kr.co.alpharking.dto.parking;

public record AiOccupancyResponse(String eventId, String spaceCode, String outcome,
                                  String previousStatus, String currentStatus,
                                  Long aiDetectionEventId) {}
