package kr.co.alpharking.dto.safety;

/** STORED / DUPLICATE; AI CLEARED does not mean the incident is RESOLVED. */
public record FireSafetyResponse(String transitionId, String outcome,
                                 Long aiDetectionEventId, Long safetyIncidentId,
                                 int notificationsCreated, boolean isTest) {}
