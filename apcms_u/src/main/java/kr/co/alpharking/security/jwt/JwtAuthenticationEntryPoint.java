package kr.co.alpharking.security.jwt;

import java.io.IOException;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.authentication.www.BasicAuthenticationEntryPoint;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;


public class JwtAuthenticationEntryPoint extends BasicAuthenticationEntryPoint{


	@Override
	public void afterPropertiesSet() {
	
		setRealmName("JWT Authentication");
		super.afterPropertiesSet();
	}

	@Override
	public void commence(HttpServletRequest request, HttpServletResponse response,
			AuthenticationException authException) throws IOException {
		
		response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);

		response.setContentType("application/json");
		response.getWriter().write("{ \"message\": \"" + authException.getMessage() + "\" }");
	}
}
