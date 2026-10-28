/** 파일 안내
 * 용도: A 소켓의 첫 AUTH에 대한 관리자 JWT·계정 검증.
 * 사용처·연결: A ParkingWebSocketHandler.authenticate → 기존 JwtTokenProvider·UserDetailsService.
 * ADMIN과 Admin principal을 검사하고 만료 시각만 Identity에 보관한다. JWT 원문은 보관하지 않는다.
 */
package kr.co.alpharking.websocket.parking;

import java.time.Instant;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.stereotype.Service;
import kr.co.alpharking.security.Admin;
import kr.co.alpharking.security.jwt.JwtTokenProvider;

/** HTTP 로그인과 동일한 JWT 키와 사용자 조회를 사용하며 토큰 원문을 보관하지 않는다. */
@Service
public class ParkingWebSocketAuthService {
    private final JwtTokenProvider tokenProvider;
    private final UserDetailsService userDetailsService;

    public ParkingWebSocketAuthService(JwtTokenProvider tokenProvider, UserDetailsService userDetailsService) {
        this.tokenProvider = tokenProvider;
        this.userDetailsService = userDetailsService;
    }

    // JWT 서명·만료·role을 검증한 뒤 기존 계정 조회와 현재 계정 상태·권한도 확인한다.
    public Identity authenticate(String token) {
        if (token == null || token.isBlank() || token.length() > 8192) {
            throw new BadCredentialsException("JWT 인증이 필요합니다.");
        }
        // getExpiration은 서명과 유효기간도 검증한다. JWT 예외는 Handler에서 연결 거절로 처리한다.
        Instant expiresAt = tokenProvider.getExpiration(token);
        String username = tokenProvider.getUsername(token);
        if (username == null || username.isBlank() || !"ADMIN".equals(tokenProvider.getRole(token))) {
            throw new BadCredentialsException("관리자 인증이 필요합니다.");
        }
        UserDetails user = userDetailsService.loadUserByUsername(username);
        if (!(user instanceof Admin admin) || admin.getAdmin_id() == null
                || !user.isEnabled() || !user.isAccountNonLocked() || !user.isAccountNonExpired()
                || !user.isCredentialsNonExpired()
                || user.getAuthorities().stream().noneMatch(authority -> "ADMIN".equals(authority.getAuthority()))
                || !expiresAt.isAfter(Instant.now())) {
            throw new BadCredentialsException("관리자 인증을 확인할 수 없습니다.");
        }
        return new Identity(user.getUsername(), expiresAt);
    }

    // 인증된 이름·만료 시각만 보관한다. 원본 토큰과 비밀 키를 세션에 남기지 않는다.
    public record Identity(String username, Instant expiresAt) {}
}
