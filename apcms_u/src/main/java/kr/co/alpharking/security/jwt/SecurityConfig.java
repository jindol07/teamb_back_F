package kr.co.alpharking.security.jwt;
import java.util.Arrays;
import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.www.BasicAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import jakarta.annotation.PostConstruct;
import jakarta.servlet.DispatcherType;

//1023: 배포 CORS 이슈
import java.util.Arrays;
import org.springframework.beans.factory.annotation.Value;

@EnableWebSecurity
@Configuration
public class SecurityConfig {
	// JWT 토큰을 검증하는 필터
	@Autowired
	private JwtTokenFilter jwtTokenFilter;
	// 사용자 상세 정보를 제공하는 서비스
	@Autowired
	private UserDetailsService userDetailsService;

	@Autowired
	private JwtAuthenticationEntryPoint jwtAuthenticationEntryPoint;

	//1023: 배포 CORS 이슈
	@Value("${app.cors.origins}")
	private String corsOrigins;
	
	
	//단방향 비밀번호 인코딩 -> 시큐리티는 데이터 베이스에 저장할 때 암호화 해서 저장
	@Bean
	public PasswordEncoder passwordEncoder() {
		return new BCryptPasswordEncoder();
	}
	
    @Bean
    public DaoAuthenticationProvider daoAuthenticationProvider() {
        DaoAuthenticationProvider provider =
                new DaoAuthenticationProvider(userDetailsService);

        provider.setPasswordEncoder(passwordEncoder());
        return provider;
    }
    // BCryptPasswordEncoder를 사용하여 비밀번호를 암호화하는 PasswordEncoder 객체를 생성
    // BCryptPasswordEncoder는 비밀번호를 안전하게 저장하기 위한 현대적인 해시 알고리즘을 사용
    @Bean
    AuthenticationManager authenticationManager(
            AuthenticationConfiguration authenticationConfiguration) throws Exception {
        return authenticationConfiguration.getAuthenticationManager();
    }
    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        		http
                .csrf((csrf) -> csrf.disable())
                .cors((cors) -> cors.configurationSource(corsConfigurationSource()))
                .formLogin((login) -> login.disable())
                .httpBasic((basic) -> basic.disable())
                .authorizeHttpRequests((auth) -> auth
                		.dispatcherTypeMatchers(DispatcherType.ERROR).permitAll()
                		.requestMatchers("/error").permitAll()
                		.requestMatchers("/api/notice/**").permitAll()
                        .requestMatchers("/api/auth/**").permitAll()
                        .requestMatchers("/demos/**").permitAll() 
                        .requestMatchers("/api/gallery/**").permitAll()
                        .requestMatchers("/api/board/**").permitAll()
                        .requestMatchers("/api/member/**").permitAll()
                        .requestMatchers("/uploads/**").permitAll()
                        .requestMatchers("/api/employees/**","/back/api/employees/**").permitAll()
                        .requestMatchers("/api/notifications", "/api/notifications/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/ws/parking/spaces").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/parking/spaces").authenticated()
                        .requestMatchers(HttpMethod.POST, "/api/recmn/recommend").authenticated()
                        .requestMatchers("/actuator/health", "/actuator/health/**").permitAll()
                        .requestMatchers("/admin/**").hasAuthority("ADMIN")
                        .requestMatchers("/user/**").hasAuthority("OFFICE")
                        .requestMatchers("/api/notice", "/api/notice/**").authenticated()
                        .anyRequest().authenticated())
                .addFilterBefore(jwtTokenFilter, 
                		BasicAuthenticationFilter.class)
                .exceptionHandling(handler -> handler
                		.authenticationEntryPoint(jwtAuthenticationEntryPoint))
                .sessionManagement((session) -> session
                		.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .logout((logout) -> logout.disable());
        return http.build();
    }
    
//1023: 배포 CORS 이슈   
//    @Bean
//    public CorsConfigurationSource corsConfigurationSource() {
//        CorsConfiguration corsConfiguration = new CorsConfiguration();
//        corsConfiguration.setAllowCredentials(true);
//        corsConfiguration.setAllowedOrigins(// React 그러니까 개발 클라이언트 접속만 허용 
//        		List.of("http://192.168.0.13:3000", "http://localhost:3000")
//        		);
//        corsConfiguration.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"));
//        corsConfiguration.setAllowedHeaders(List.of("*"));
//
//        UrlBasedCorsConfigurationSource urlBasedCorsConfigurationSource = new UrlBasedCorsConfigurationSource();
//        urlBasedCorsConfigurationSource.registerCorsConfiguration("/**", corsConfiguration);
//
//        return urlBasedCorsConfigurationSource;
//
//    }// corsConfigurationSource
    
//1023: 배포 CORS 이슈
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {

        CorsConfiguration corsConfiguration = new CorsConfiguration();

        // 쿠키 등 인증 정보가 포함된 요청 허용
        corsConfiguration.setAllowCredentials(true);
        // 운영/개발 오리진은 application.properties(app.cors.origins)에서 관리한다.
        corsConfiguration.setAllowedOrigins(
                Arrays.asList(corsOrigins.split("\\s*,\\s*"))
        );
        corsConfiguration.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"));
        // application.properties 또는 환경변수에서 허용 Origin 읽기
        corsConfiguration.setAllowedOrigins(
            Arrays.stream(corsOrigins.split(","))
                .map(String::trim)
                .filter(origin -> !origin.isEmpty())
                .toList()
        );

        // 허용 HTTP 메서드
        corsConfiguration.setAllowedMethods(
            List.of("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS")
        );

        // 요청 헤더 허용
        corsConfiguration.setAllowedHeaders(List.of("*"));

        // 응답에서 필요한 헤더 노출
        corsConfiguration.setExposedHeaders(
            List.of("Authorization")
        );

        UrlBasedCorsConfigurationSource source =
            new UrlBasedCorsConfigurationSource();

        source.registerCorsConfiguration("/**", corsConfiguration);

        return source;
    }
    

}





