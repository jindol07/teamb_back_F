package kr.co.alpharking.auth;

import java.security.SecureRandom;
import java.time.Duration;
import java.util.Base64;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dao.auth.RefreshTokenRedisDao;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.security.jwt.AuthResponse;
import kr.co.alpharking.security.jwt.JwtTokenProvider;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class AuthTokenService {

    private static final int REFRESH_TOKEN_BYTES = 32;

    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenRedisDao refreshTokenRedisDao;
    private final UserDetailsService userDetailsService;
    private final SecureRandom secureRandom = new SecureRandom();

    @Value("${app.jwt.refresh-millis}")
    private long refreshMillis;

    @Value("${app.auth.admin-active-status}")
    private String adminActiveStatus;

    /** 관리자 로그인 성공 시 access + refresh를 함께 발급한다. */
    public AuthResponse issue(Authentication authentication) {
        String accessToken = jwtTokenProvider.createToken(authentication);
        String refreshToken = newRefreshToken();

        refreshTokenRedisDao.save(
                refreshToken,
                authentication.getName(),
                Duration.ofMillis(refreshMillis));

        return new AuthResponse(
                accessToken,
                refreshToken,
                "Bearer",
                jwtTokenProvider.getAccessValidityMillis() / 1000);
    }

    /** 기존 refresh를 1회용으로 소비하고 새 토큰 쌍을 발급한다(회전). */
    public AuthResponse refresh(String rawRefreshToken) {
        if (!StringUtils.hasText(rawRefreshToken)) {
            throw unauthorized("리프레시 토큰이 없습니다.");
        }

        String username = refreshTokenRedisDao.consume(rawRefreshToken)
                .orElseThrow(() -> unauthorized("리프레시 토큰이 유효하지 않습니다."));

        UserDetails user;
        try {
            user = userDetailsService.loadUserByUsername(username);
        } catch (UsernameNotFoundException e) {
            throw unauthorized("리프레시 토큰의 관리자를 찾을 수 없습니다.");
        }

        // 관리자 계정 상태가 ACTIVE가 아니면 refresh를 거부한다.
        if (user instanceof Admin admin
                && !adminActiveStatus.equals(admin.getStatus_code())) {
            throw unauthorized("사용할 수 없는 관리자 계정입니다.");
        }

        Authentication authentication =
                new UsernamePasswordAuthenticationToken(user, null, user.getAuthorities());

        return issue(authentication);
    }

    public void logout(String rawRefreshToken) {
        if (StringUtils.hasText(rawRefreshToken)) {
            refreshTokenRedisDao.delete(rawRefreshToken);
        }
    }

    private String newRefreshToken() {
        byte[] bytes = new byte[REFRESH_TOKEN_BYTES];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private ResponseStatusException unauthorized(String message) {
        return new ResponseStatusException(HttpStatus.UNAUTHORIZED, message);
    }
}
