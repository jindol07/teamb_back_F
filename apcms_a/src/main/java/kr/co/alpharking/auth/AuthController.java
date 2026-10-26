package kr.co.alpharking.auth;

import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;

import kr.co.alpharking.security.Admin;
import kr.co.alpharking.security.jwt.AuthRequest;
import kr.co.alpharking.security.jwt.AuthResponse;
import lombok.extern.slf4j.Slf4j;

@RestController
@CrossOrigin
@RequestMapping("/api/auth")
@Slf4j
public class AuthController {
	@Autowired
	private AuthenticationManager authenticationManager;

	@Autowired
	private AuthTokenService authTokenService;
	
//	@Autowired
//	private RestTemplate restTemplate;

	@PostMapping("/login")
	public ResponseEntity<?> authenticateUser(@RequestBody AuthRequest authRequest) {
		try {
			Authentication authentication = authenticationManager.authenticate(
					new UsernamePasswordAuthenticationToken(authRequest.getUsername(), authRequest.getPassword()));

			SecurityContextHolder.getContext().setAuthentication(authentication);

			return ResponseEntity.ok(authTokenService.issue(authentication));
		} catch (AuthenticationException e) {
			log.warn("관리자 로그인 실패: {}", authRequest.getUsername());
			return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
					.body(Map.of("message", "아이디 또는 비밀번호가 올바르지 않습니다."));
		}
	}

	@PostMapping("/refresh")
	public ResponseEntity<AuthResponse> refresh(@RequestBody(required = false) Map<String, String> body) {
		String refreshToken = body == null ? null : body.get("refresh_token");
		return ResponseEntity.ok(authTokenService.refresh(refreshToken));
	}

	// 기존 클라이언트 호환용 로그아웃
	@GetMapping("/logout")
	public ResponseEntity<?> logoutUser() {
		SecurityContextHolder.clearContext();
		return ResponseEntity.ok("Logout successful");
	}

	// 관리자 정보
	@GetMapping("/admin")
	public ResponseEntity<?> getOfficeInfo(@AuthenticationPrincipal Admin admin) {
		if (admin == null) {
			return ResponseEntity.status(401).body("로그인이 필요합니다.");
		}
		return ResponseEntity.ok(admin);
	}

	/** refresh 토큰을 Redis에서 삭제해 재발급을 막는다. */
	@PostMapping("/logout")
	public ResponseEntity<Void> logout(@RequestBody(required = false) Map<String, String> body) {
		authTokenService.logout(body == null ? null : body.get("refresh_token"));
		SecurityContextHolder.clearContext();
		return ResponseEntity.noContent().build();
	}
	
	
//	// naver
//	@GetMapping("/naver")
//	public ResponseEntity<String> naverLogin() {
//		restTemplate.getForEntity("https://nid.naver.com/oauth2.0/authorize", );
//	}
}
