package kr.co.alpharking.dao.auth;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;
import java.util.Optional;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import lombok.RequiredArgsConstructor;

@Repository
@RequiredArgsConstructor
public class RefreshTokenRedisDao {
    /** 사용자 앱 전용 prefix. 관리자 앱은 auth:refresh:a: 를 사용한다. */
    private static final String KEY_PREFIX = "auth:refresh:u:";

    private final StringRedisTemplate redisTemplate;

    public void save(String rawToken, String username, Duration ttl) {
        redisTemplate.opsForValue().set(key(rawToken), username, ttl);
    }

    /** 조회와 삭제를 원자적으로 처리해 동시 재사용을 막는다. */
    public Optional<String> consume(String rawToken) {
        return Optional.ofNullable(redisTemplate.opsForValue().getAndDelete(key(rawToken)));
    }

    public void delete(String rawToken) {
        redisTemplate.delete(key(rawToken));
    }

    private String key(String rawToken) {
        return KEY_PREFIX + sha256(rawToken);
    }

    private String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 해시를 사용할 수 없습니다.", e);
        }
    }
}