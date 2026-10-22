package kr.co.alpharking.service.safety;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/**
 * 임시 공간 그룹화 정책. Python의 세션 ID가 바뀌어도 같은 카메라/격자/위험 유형이면
 * 관리자가 아직 해결하지 않은 사건에 연결합니다. 정확한 주차면 또는 실제 공간 매핑은 별도 과제입니다.
 */
public final class FireSafetyGroupKey {
    private static final int GRID_SIZE = 256;
    private FireSafetyGroupKey() {}

    public static String sha256(String value) {
        try {
            byte[] bytes = MessageDigest.getInstance("SHA-256")
                .digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(bytes);
        } catch (NoSuchAlgorithmException ex) { throw new IllegalStateException(ex); }
    }

    public static String group(String sourceKind, String sourceName, String hazard,
                               int x1, int y1, int x2, int y2, boolean test) {
        long centerX = ((long)x1 + x2) / 2;
        long centerY = ((long)y1 + y2) / 2;
        String parts = String.join("\n", "fire-safety-grid-v1", sourceKind, sourceName,
                hazard, Long.toString(centerX / GRID_SIZE), Long.toString(centerY / GRID_SIZE),
                test ? "TEST" : "LIVE");
        return sha256(parts);
    }
}
