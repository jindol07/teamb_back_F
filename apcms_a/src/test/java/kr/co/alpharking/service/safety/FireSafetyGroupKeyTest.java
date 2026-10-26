package kr.co.alpharking.service.safety;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class FireSafetyGroupKeyTest {
    @Test void deterministic() {
        String a = FireSafetyGroupKey.group("CAMERA", "camera_0", "FIRE", 0, 0, 200, 200, true);
        String b = FireSafetyGroupKey.group("CAMERA", "camera_0", "FIRE", 0, 0, 200, 200, true);
        assertEquals(a, b);
        assertEquals(64, a.length());
    }
    @Test void reuseWhenSessionChanges() {
        String a = FireSafetyGroupKey.group("CAMERA", "camera_0", "FIRE", 32, 40, 192, 210, true);
        String b = FireSafetyGroupKey.group("CAMERA", "camera_0", "FIRE", 48, 50, 184, 212, true);
        assertEquals(a, b);
    }
    @Test void independentDualFireLocations() {
        var a = FireSafetyGroupKey.group("VIDEO", "dual_fire_sequence.mp4", "FIRE", 112, 1, 493, 539, true);
        var b = FireSafetyGroupKey.group("VIDEO", "dual_fire_sequence.mp4", "FIRE", 819, 1, 1160, 539, true);
        assertNotEquals(a, b);
    }
    @Test void doNotMixHazardsAndModesAndSources() {
        String original = FireSafetyGroupKey.group("CAMERA", "camera_0", "FIRE", 30, 40, 210, 210, true);
        assertNotEquals(original, FireSafetyGroupKey.group("CAMERA", "camera_0", "SMOKE", 30, 40, 210, 210, true));
        assertNotEquals(original, FireSafetyGroupKey.group("CAMERA", "camera_0", "FIRE", 30, 40, 210, 210, false));
        assertNotEquals(original, FireSafetyGroupKey.group("CAMERA", "camera_1", "FIRE", 30, 40, 210, 210, true));
    }
    @Test void crossGridIsNewArea() {
        String a = FireSafetyGroupKey.group("CAMERA", "camera_0", "FIRE", 1, 1, 100, 100, true);
        String b = FireSafetyGroupKey.group("CAMERA", "camera_0", "FIRE", 800, 1, 900, 100, true);
        assertNotEquals(a,b);
    }
}
