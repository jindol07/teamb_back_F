package kr.co.alpharking.auth;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Iterator;
import java.util.Map;

import java.sql.Date;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.dto.auth.SignupRequest;
import kr.co.alpharking.dto.auth.SignupResponse;
import kr.co.alpharking.security.Company;
import kr.co.alpharking.security.CompanyRepository;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.security.UserRepository;
import kr.co.alpharking.security.SignupVehicle;
import kr.co.alpharking.security.SignupVehicleRepository;
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
	private PasswordEncoder passwordEncoder;
	@Autowired
	private UserRepository userRepository;
	@Autowired
	private CompanyRepository companyRepository;
	@Autowired
	private SignupVehicleRepository vehicleRepository;
	@Autowired
	private AuthTokenService authTokenService;
	// 네이버 로그인 (회원가입 없이 기존 회원만 로그인)
	@Autowired
	private NaverOAuthService naverOAuthService;

	@PostMapping("/login")
	public ResponseEntity<?> authenticateUser(@RequestBody AuthRequest authRequest) {
		try {
			Authentication authentication = authenticationManager.authenticate(
					new UsernamePasswordAuthenticationToken(authRequest.getUsername(), authRequest.getPassword()));

			SecurityContextHolder.getContext().setAuthentication(authentication);

			return ResponseEntity.ok(authTokenService.issue(authentication));
		} catch (AuthenticationException e) {
			log.warn("로그인 실패: {}", authRequest.getUsername());
			return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("message", "아이디 또는 비밀번호가 올바르지 않습니다."));
		}
	}

	@PostMapping("/refresh")
	public ResponseEntity<AuthResponse> refresh(@RequestBody(required = false) RefreshRequest request) {
		String refreshToken = request == null ? null : request.refreshToken();
		return ResponseEntity.ok(authTokenService.refresh(refreshToken));
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

	// 사용자 정보
	@GetMapping("/office")
	public ResponseEntity<?> getOfficeInfo(@AuthenticationPrincipal Office office) {
		if (office == null) {
			return ResponseEntity.status(401).body("로그인이 필요합니다.");
		}
		return ResponseEntity.ok(office);
	}

	// 회원가입
	@Transactional(rollbackFor = Exception.class)
	@PostMapping("/signup")
	public ResponseEntity<?> OfficeSignup(@RequestBody SignupRequest req) {
		System.out.println(123123);
		System.out.println(req.getFloor_no());

		if (req == null) {
			return ResponseEntity.badRequest().body(new SignupResponse("xxx"));
		}

		boolean duplicated = userRepository.existsDuplicateOffice(req.getCompany_id(), req.getFloor_no(),
				req.getOffice_number());

		if (duplicated) {
			return ResponseEntity.badRequest().body("해당 회사에 이미 등록된 층수와 호수입니다.");
		}

		try {
			LocalDateTime currentDate = LocalDateTime.now();

			Company company = companyRepository.save(Company.builder().company_name(req.getCompany_company_name())
					.business_number(req.getCompany_business_number()).company_addr(req.getCompany_company_addr())
					.status_code("ACTIVE").created_at(currentDate).updated_at(currentDate).build());

			Office office = userRepository.save(Office.builder().username(req.getUsername())
					.password(passwordEncoder.encode(req.getPassword())).email(req.getEmail().trim())
					.phone(req.getPhone().trim()).company_id(company.getCompany_id()).floor_no(req.getFloor_no())
					.office_number(req.getOffice_number().trim()).status_code("ACTIVE").created_at(currentDate)
					.updated_at(currentDate).build());

			System.out.println(111111111);
			System.out.println(req.getVehicle_list());

			for (SignupVehicle v : req.getVehicle_list()) {
				SignupVehicle vehicle = SignupVehicle.builder().office_id(office.getOffice_id())
						.vehicle_number(v.getVehicle_number()).vehicle_model(null).owner_name(v.getOwner_name())
						.vehicle_type_code(v.getVehicle_type_code()).registration_type_code("INITIAL")
						.registration_status_code("APPROVED").registered_at(currentDate).rejected_reason(null)
						.created_at(currentDate).updated_at(currentDate).deleted_at(null).build();

				vehicleRepository.save(vehicle);
				System.out.println(vehicle);
			}

//        	userRepository.saveAndFlush(office);
			System.out.println(office);
//        	companyRepository.saveAndFlush(company);
			System.out.println(office);
			return ResponseEntity.status(HttpStatus.CREATED).body(new SignupResponse("회원가입이 완료되었습니다."));
		} catch (DataIntegrityViolationException e) {
			e.printStackTrace();
		}

		return ResponseEntity.ok(new SignupResponse("정상적으로 가입 되었습니다."));
	}

	// 아이디 중복 체크
	@GetMapping("/check-username")
	public ResponseEntity<Boolean> checkLoginId(@RequestParam("username") String username) {
		boolean duplicated = userRepository.findByUsername(username).isPresent();
		System.out.println(duplicated);
		return ResponseEntity.ok(duplicated);
	}

	@GetMapping("/check-email")
	public ResponseEntity<Boolean> checkEmail(@RequestParam("email") String email) {
		boolean duplicated = !userRepository.findByEmailIgnoreCase(email).isEmpty();
		return ResponseEntity.ok(duplicated);
	}

	@GetMapping("/check-business")
	public ResponseEntity<Boolean> checkBusiness(@RequestParam("business_number") String business_number) {
		boolean duplicated = companyRepository.existsDuplicateBusinessNumber(business_number.trim());
		return ResponseEntity.ok(duplicated);
	}
	
	@GetMapping("/check-vehicle")
	public ResponseEntity<Boolean> checkVehicle(@RequestParam("vehicle_number") String vehicle_number) {
	    boolean duplicated = vehicleRepository.countDuplicateVehicleNumber(vehicle_number.trim()) > 0;
	    return ResponseEntity.ok(duplicated);
	}

	/** refresh 토큰을 Redis에서 삭제해 재발급을 막는다. */
	@PostMapping("/logout")
	public ResponseEntity<Void> logout(@RequestBody(required = false) RefreshRequest request) {
		authTokenService.logout(request == null ? null : request.refreshToken());
		SecurityContextHolder.clearContext();
		return ResponseEntity.noContent().build();
	}

	// ------------------------------------------------------------------
	// 네이버 로그인 (회원가입 없이 기존 회원만 로그인)
	// ------------------------------------------------------------------

	/** 네이버 authorize URL을 반환한다. state는 서버(Redis)에 5분간 보관된다. */
	@GetMapping("/naver/authorize")
	public ResponseEntity<?> naverAuthorize() {
		try {
			return ResponseEntity.ok(new NaverAuthorizeResponse(naverOAuthService.createAuthorizeUrl()));
		} catch (ResponseStatusException e) {
			return naverError(e);
		}
	}

	/** 콜백의 code/state를 검증하고 기존 회원에게 우리 서비스 토큰을 발급한다. */
	@PostMapping("/naver/login")
	public ResponseEntity<?> naverLogin(@RequestBody(required = false) NaverLoginRequest request) {
		if (request == null) {
			return ResponseEntity.badRequest().body(Map.of("message", "요청 본문이 없습니다."));
		}

		try {
			return ResponseEntity.ok(naverOAuthService.login(request.code(), request.state()));
		} catch (ResponseStatusException e) {
			return naverError(e);
		}
	}

	/**
	 * 네이버 로그인 실패 사유를 로그인 화면에서 그대로 보여주기 위한 응답. 기존 /login, /refresh, /logout 응답 형식은
	 * 건드리지 않는다.
	 */
	private ResponseEntity<Map<String, Object>> naverError(ResponseStatusException e) {
		String message = e.getReason() == null ? "네이버 로그인에 실패했습니다." : e.getReason();
		return ResponseEntity.status(e.getStatusCode()).body(Map.of("message", message));
	}

	/** /naver/login 요청 본문. */
	public record NaverLoginRequest(String code, String state) {
	}

	/** /naver/authorize 응답. SNAKE_CASE 설정으로 authorize_url 로 내려간다. */
	public record NaverAuthorizeResponse(String authorizeUrl) {
	}

	/** /refresh, /logout 요청 본문. SNAKE_CASE 전략으로 refresh_token 과 매핑된다. */
	public record RefreshRequest(String refreshToken) {
	}
}
