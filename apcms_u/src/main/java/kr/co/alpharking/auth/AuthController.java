package kr.co.alpharking.auth;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Iterator;
import java.sql.Date;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
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
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

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
	@Autowired
	private UserRepository userRepository;
	@Autowired
	private CompanyRepository companyRepository;
	@Autowired
	private SignupVehicleRepository vehicleRepository;
	
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
			
			return ResponseEntity.ok(new AuthResponse(jwt));
		} catch (Exception e) {
			System.out.println("인증 오류   :  " + e);
		}
		// AuthenticationResponse에 JWT 토큰을 담아 클라이언트에게 반환
		return ResponseEntity.ok(new AuthResponse(null));
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
    @PostMapping("/signup")
    public ResponseEntity<SignupResponse> OfficeSignup(@RequestBody SignupRequest req) {
    	System.out.println(123123);
    	System.out.println(req.getFloor_no());
    	
        if (req == null) {
            return ResponseEntity.badRequest().body(new SignupResponse("xxx"));
        }
                
        try {
        	LocalDateTime currentDate = LocalDateTime.now();
        	
            Company company = companyRepository.save(
        		Company.builder()
	        		.company_name(req.getCompany_company_name())
	        		.business_number(req.getCompany_business_number())
	        		.company_addr(req.getCompany_company_addr())
	        		.status_code("ACTIVE")
		            .created_at(currentDate)
		            .updated_at(currentDate)
	        		.build()
    		);
	        
	        Office office =  userRepository.save(
        		Office.builder()
		            .username(req.getUsername())
		            .password(passwordEncoder.encode(req.getPassword()))
		            .email(req.getEmail().trim())
		            .phone(req.getPhone().trim())
		            .company_id(company.getCompany_id())
		            .floor_no(req.getFloor_no())
		            .office_number(req.getOffice_number().trim())
		            .status_code("ACTIVE")
		            .created_at(currentDate)
		            .updated_at(currentDate)
		            .build()
	        );
	        
	        System.out.println(111111111);
	        System.out.println(req.getVehicle_list());
	        System.out.println(111111111);
	        
	        for (SignupVehicle v : req.getVehicle_list()) {
	        	SignupVehicle vehicle = SignupVehicle.builder()
		        		.office_id(office.getOffice_id())
		        		.vehicle_number(v.getVehicle_number())
		        		.vehicle_model(null)
		        		.owner_name(v.getOwner_name())
		        		.vehicle_type_code(v.getVehicle_type_code())
		        		.registration_type_code("INITIAL")
		        		.registration_status_code("APPROVED")
		        		.registered_at(currentDate)
		        		.rejected_reason(null)
		        		.created_at(currentDate)
		        		.updated_at(currentDate)
		        		.deleted_at(null)
		        		.build();
	        	
	        	vehicleRepository.save(vehicle);
	        	System.out.println(vehicle);
	        }
	        
        	
//        	userRepository.saveAndFlush(office);
        	System.out.println(office);
//        	companyRepository.saveAndFlush(company);
        	System.out.println(office);
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(new SignupResponse(
                            "회원가입이 완료되었습니다."
                    ));
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
}
