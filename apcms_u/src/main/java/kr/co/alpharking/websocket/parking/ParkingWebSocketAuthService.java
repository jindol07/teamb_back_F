package kr.co.alpharking.websocket.parking;

import java.time.Instant;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.stereotype.Service;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.security.jwt.JwtTokenProvider;

/** U 로그인 JWT와 기존 Office 조회를 사용하며 토큰 원문을 보관하지 않는다. */
@Service
public class ParkingWebSocketAuthService {
    private final JwtTokenProvider tokenProvider;
    private final UserDetailsService userDetailsService;

    public ParkingWebSocketAuthService(JwtTokenProvider tokenProvider, UserDetailsService userDetailsService) {
        this.tokenProvider = tokenProvider;
        this.userDetailsService = userDetailsService;
    }

    public Identity authenticate(String token) {
        if (token == null || token.isBlank() || token.length() > 8192) {
            throw new BadCredentialsException("JWT 인증이 필요합니다.");
        }
        Instant expiresAt = tokenProvider.getExpiration(token);
        String username = tokenProvider.getUsername(token);
        if (username == null || username.isBlank() || !"OFFICE".equals(tokenProvider.getRole(token))) {
            throw new BadCredentialsException("사용자 인증이 필요합니다.");
        }
        UserDetails user = userDetailsService.loadUserByUsername(username);
        if (!(user instanceof Office office) || office.getOffice_id() == null
                || !user.isEnabled() || !user.isAccountNonLocked() || !user.isAccountNonExpired()
                || !user.isCredentialsNonExpired()
                || user.getAuthorities().stream().noneMatch(authority -> "OFFICE".equals(authority.getAuthority()))
                || !expiresAt.isAfter(Instant.now())) {
            throw new BadCredentialsException("사용자 인증을 확인할 수 없습니다.");
        }
        return new Identity(user.getUsername(), expiresAt);
    }

    public record Identity(String username, Instant expiresAt) {}
}
