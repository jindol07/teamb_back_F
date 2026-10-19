package kr.co.alpharking.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class SecurityConfig {
	@Bean
	public SecurityFilterChain securityFilterChain(HttpSecurity http) {
		http.csrf(csrf-> csrf.disable())
//		.authorizeHttpRequests(
//				auth-> auth.requestMatchers("/api/employees/**").permitAll()
//				.anyRequest().authenticated()
//				)
		.authorizeHttpRequests(
				auth-> auth.requestMatchers("/","/main").permitAll()
				.requestMatchers("/api/employees/**").permitAll()
				// hasAuthority("커스터마이징한Role") => Role_Admin 만들어 주는데 귀찮으니까 enum으로 지정해놓고 변경 해준것
				.requestMatchers("/admin/**").hasAuthority("ADMIN") // 우리가 커스터마이징을 한 경우 사용 Role을 비교 *****
				.anyRequest().authenticated()// 다른 모든 요청은 인증 필요
				)
		.formLogin(form -> form.loginPage("/login").permitAll())
		.logout(logout -> logout.logoutUrl("/logout")
				.logoutSuccessUrl("/login?logout")
				.permitAll() 
				);
		return http.build();
	}
	@Bean
	public PasswordEncoder passwordEncoder() {
		return new BCryptPasswordEncoder();
	}
}




