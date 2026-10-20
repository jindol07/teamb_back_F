package kr.co.alpharking.auth;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.security.Office;
import kr.co.alpharking.security.jwt.AuthRequest;
import kr.co.alpharking.security.jwt.AuthResponse;
import kr.co.alpharking.security.jwt.JwtTokenProvider;

@RestController
@CrossOrigin
@RequestMapping("/api/auth")
public class AuthController {
	@Autowired
	private AuthenticationManager authenticationManager;

	@Autowired
	private JwtTokenProvider jwtTokenProvider;

	@Autowired
	private PasswordEncoder passwordEncoder;

	@PostMapping("/login")
	public ResponseEntity<?> authenticateUser(@RequestBody AuthRequest authRequest) {
		System.out.println("authenticationRequest getUsername-------------------> " + authRequest.getUsername());
		System.out.println("authenticationRequest getPassword -------------------> " + authRequest.getPassword());
		try {
			// 사용자가 입력한 비밀번호와 데이터베이스에 저장된 암호화된 비밀번호를 비교하여 일치 여부를 확인하는 단계를 거쳐서 맞으면 Authentication를 생성한다. 틀리면 예외를 발생시킨다.
			Authentication authentication = authenticationManager.authenticate(
					new UsernamePasswordAuthenticationToken(authRequest.getUsername(), authRequest.getPassword()));
			System.out.println("인증 성공 여부:" + authentication);
			System.out.println("Authentication 호출 후");
			// 인증 성공 시, SecurityContextHolder에 인증 정보를 설정한다.
			SecurityContextHolder.getContext().setAuthentication(authentication);
			System.out.println("SecurityContextHolder 호출 후");
			// JwtTokenProvider를 사용하여 JWT 토큰을 생성
			String jwt = jwtTokenProvider.createToken(authentication);
			System.out.print("jwtLog~~~~~~~ =>" + jwt);
			
			Office userDetails = (Office) authentication.getPrincipal();
			String officeNumber = userDetails.getOfficeNumber();
			
			return ResponseEntity.ok(new AuthResponse(jwt, officeNumber));
		} catch (Exception e) {
			System.out.println("인증 오류   :  " + e);
		}
		// AuthenticationResponse에 JWT 토큰을 담아 클라이언트에게 반환
		return ResponseEntity.ok(new AuthResponse(null, null));
	}

	// 사용자 로그아웃 처리
	@GetMapping("/logout")
	public ResponseEntity<?> logoutUser() {
		// 실제로 JWT 토큰 기반 인증에서 로그아웃은 클라이언트 측에서 토큰을 삭제하는 것으로 처리되지만,
		// 서버 측에서는 SecurityContextHolder의 컨텍스트를 클리어 해야 한다.
		SecurityContextHolder.clearContext();
		System.out.println("Token을 삭제 했습니다.");
		return ResponseEntity.ok("Logout successful");
	}

//	// 사용자 정보
//    @GetMapping("/office")
//    public ResponseEntity<?> getOfficeInfo(@AuthenticationPrincipal Office office) {
//        if (office == null) {
//            return ResponseEntity.status(401).body("로그인이 필요합니다.");
//        }
//        return ResponseEntity.ok(office);
//    }
}
