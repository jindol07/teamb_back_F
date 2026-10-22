package kr.co.alpharking.dao.auth;

import java.time.Duration;
import java.util.Locale;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import lombok.RequiredArgsConstructor;

@Repository
@RequiredArgsConstructor
public class EmailVerificationRedisDao {

    private static final Duration CODE_TTL = Duration.ofMinutes(5);
    private static final Duration VERIFIED_TTL = Duration.ofMinutes(10);

    private final StringRedisTemplate redisTemplate;

    public void saveCode(String email, String code) {
        redisTemplate.opsForValue()
                .set(codeKey(email), code, CODE_TTL);

        redisTemplate.opsForValue()
                .set(attemptKey(email), "0", CODE_TTL);
    }

    public String getCode(String email) {
        return redisTemplate.opsForValue().get(codeKey(email));
    }

    public boolean hasCode(String email) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(codeKey(email)));
    }

    public void increaseAttemptCount(String email) {
        String key = attemptKey(email);

        Long count = redisTemplate.opsForValue().increment(key);

        if (count != null && count == 1L) {
            redisTemplate.expire(key, CODE_TTL);
        }
    }

    public int getAttemptCount(String email) {
        String value = redisTemplate.opsForValue().get(attemptKey(email));

        return value == null ? 0 : Integer.parseInt(value);
    }

    public void deleteCodeAndAttempts(String email) {
        redisTemplate.delete(codeKey(email));
        redisTemplate.delete(attemptKey(email));
    }

    public void markEmailVerified(String email) {
        redisTemplate.opsForValue()
                .set(verifiedKey(email), "true", VERIFIED_TTL);
    }

    public boolean isEmailVerified(String email) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(verifiedKey(email)));
    }

    public void consumeEmailVerified(String email) {
        redisTemplate.delete(verifiedKey(email));
    }

    private String codeKey(String email) {
        return "email-auth:code:" + normalizeEmail(email);
    }

    private String attemptKey(String email) {
        return "email-auth:attempt:" + normalizeEmail(email);
    }

    private String verifiedKey(String email) {
        return "email-auth:verified:" + normalizeEmail(email);
    }

    private String normalizeEmail(String email) {
        return email.trim().toLowerCase(Locale.ROOT);
    }
}