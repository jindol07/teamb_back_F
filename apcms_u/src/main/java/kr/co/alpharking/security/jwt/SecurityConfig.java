package kr.co.alpharking.security.jwt;
import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
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

@EnableWebSecurity
@Configuration
public class SecurityConfig {
	// JWT 토큰을 검증하는 필터
	@Autowired
	private JwtTokenFilter jwtTokenFilter;
	// 사용자 상세 정보를 제공하는 서비스
	@Autowired
	private UserDetailsService userDetailsService;
	
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
                //리액트와 크로스 통신 및 리액트의 view를 사용 
                .cors((cors) -> cors.configurationSource(corsConfigurationSource()))
                .formLogin((login) -> login.disable())
                .httpBasic((basic) -> basic.disable())
            	//.authenticationProvider(daoAuthenticationProvider())
                .authorizeHttpRequests((auth) -> auth
                		.requestMatchers("/api/notice/**").permitAll()
                        .requestMatchers("/api/auth/**").permitAll() // /api/auth/** 에서 오는 모든 요청은 허용
                        .requestMatchers("/demos/**").permitAll() 
                        .requestMatchers("/api/gallery/**").permitAll()
                        .requestMatchers("/api/board/**").permitAll()
                        .requestMatchers("/api/member/**").permitAll()
                        .requestMatchers("/uploads/**").permitAll() //이미지 경로도 열어줘야 한다.
                        .requestMatchers("/api/employees/**","/back/api/employees/**").permitAll()
                        // 주차 소켓은 첫 AUTH 메시지에서 JWT를 검증한다. 인증 전 현황 전송은 금지한다.
                        .requestMatchers(HttpMethod.GET, "/ws/parking/spaces").permitAll()
                        // 사용자 주차현황은 기존과 동일하게 로그인한 사용자만 조회한다.
                        .requestMatchers(HttpMethod.GET, "/api/parking/spaces").authenticated()
                        //.requestMatchers("/api/chatbot/**").permitAll()
                        
                        
                        // 관리자 및 사용자 권한
                        .requestMatchers("/admin/**").hasAuthority("ADMIN")
                        .requestMatchers("/user/**").hasAuthority("OFFICE")

                        // 공지사항은 로그인한 사용자만 접근
                        .requestMatchers("/api/notice", "/api/notice/**").authenticated()
                        
                        
                        
                        .anyRequest().authenticated()) // 모든 요청에 대해 인증을 요구
                // JWT 토큰 필터 추가: JwtTokenFilter를 BasicAuthenticationFilter 전에 추가하여 JWT 토큰을 검증
                .addFilterBefore(jwtTokenFilter, BasicAuthenticationFilter.class)
                // 세션 정책 설정: SessionCreationPolicy.STATELESS로 설정하여 세션 기반 인증을 사용하지 않도록 한다.
                .sessionManagement((session) -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                // 로그아웃 기능 비활성화: 상태를 유지하지 않는 인증 방식에서는 로그아웃이 필요 없다.
                .logout((logout) -> logout.disable());
        		
        return http.build();
    }
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration corsConfiguration = new CorsConfiguration();
        corsConfiguration.setAllowCredentials(true);
        corsConfiguration.setAllowedOrigins(// React 그러니까 개발 클라이언트 접속만 허용 
        		List.of("http://192.168.0.108:3000", "http://localhost:3000")
        		);
        corsConfiguration.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"));
        corsConfiguration.setAllowedHeaders(List.of("*"));

        UrlBasedCorsConfigurationSource urlBasedCorsConfigurationSource = new UrlBasedCorsConfigurationSource();
        urlBasedCorsConfigurationSource.registerCorsConfiguration("/**", corsConfiguration);

        return urlBasedCorsConfigurationSource;

    }// corsConfigurationSource

}





