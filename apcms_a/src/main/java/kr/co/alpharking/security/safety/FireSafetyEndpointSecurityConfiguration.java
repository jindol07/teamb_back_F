package kr.co.alpharking.security.safety;

import kr.co.alpharking.security.jwt.JwtTokenFilter;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

/**
 * 기존 SecurityConfig / JwtTokenFilter 수정 없이 화재 AI POST만 별도 인증 체인으로 분리합니다.
 * POST 본문은 Controller가 공유키로 검증합니다. GET 조회는 기존 JWT 체인이 처리합니다.
 */
@Configuration
public class FireSafetyEndpointSecurityConfiguration {
    @Bean
    @Order(1)
    public SecurityFilterChain fireSafetyIngestChain(HttpSecurity http) throws Exception {
        http.securityMatcher(request -> "POST".equals(request.getMethod())
                  && "/api/parking/ai/fire-alerts".equals(request.getServletPath()))
            .csrf(csrf -> csrf.disable())
            .cors(cors -> cors.disable())
            .formLogin(login -> login.disable())
            .httpBasic(basic -> basic.disable())
            .authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS));
        return http.build();
    }

    /**
     * JwtTokenFilter는 @Component라 서블릿 필터로 자동 등록될 수 있습니다.
     * 기존 SecurityConfig 내부의 명시적 등록만 남겨 AI 공유키가 JWT 로그에 찍히지 않게 합니다.
     */
    @Bean
    public FilterRegistrationBean<JwtTokenFilter> fireSafetyDisableDuplicateJwtServletFilter(
            JwtTokenFilter filter) {
        FilterRegistrationBean<JwtTokenFilter> registration = new FilterRegistrationBean<>(filter);
        registration.setEnabled(false);
        return registration;
    }
}
