package kr.co.alpharking.security.jwt;

import java.io.IOException;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.GenericFilterBean;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.AllArgsConstructor;

//JWT 인증을 위한 클래스이다.
//OncePerRequestFilter를 상속받아 구현되며, HTTP 요청이 서버에 도착할 때마다 JWT 토큰을 검증하는 역할
@Component
@AllArgsConstructor
public class JwtTokenFilter extends OncePerRequestFilter{
	//JWT 토큰을 만들고 검증하는데 사용
	private JwtTokenProvider jwtTokenProvider;
	
	//시큐리티에서 사용자의 상세정보 
	private UserDetailsService userDetailsService;

	//Filter의 개념을 이해 했다면 언제 호출이 되나요??
	//요청이 올때 마다 스프링의 컨트럴로 요청일 가기 전 / 후 
	@Override
	protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
			throws ServletException, IOException {
		// Get the JWT token from the Authorization header
		// 토큰 추출: jwtTokenProvider.resolveToken(request)를 호출하여 HTTP 요청의 헤더에서 JWT 토큰을 추출
        String token = jwtTokenProvider.resolveToken(request);
        //처음 로그인 하면 여기는 null이다.
        //로그인 -> 인증처리 -> 발급한 토큰을 받았을 때 null이 아님
        System.out.println("JwtTokenFilter token============>"+token);
        if (token != null && jwtTokenProvider.validateToken(token)) {

            String username = jwtTokenProvider.getUsername(token);
            //JwtTokenFilter: 추출된 username => xman2@gmail.com
            System.out.println("JwtTokenFilter: 추출된 username => " + username);
            
            //---Token으로 부터 getRole 해서 롤 출력 ------------------------------------
            String role = jwtTokenProvider.getRole(token);
            System.out.println("Role: " + role);
            
            //----------------------------------------------------------------------
           // Get the user details from the token
            UserDetails userDetails = userDetailsService.loadUserByUsername(jwtTokenProvider.getUsername(token));
          //Create an authentication object and set it in the security context holder
            UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                    userDetails, null, userDetails.getAuthorities());
           // 생성된 인증 객체를 SecurityContextHolder에 설정하여,
            authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
            // 이후의 요청 처리 과정에서 현재 사용자가 인증되었음을 SecurityContextHolder를 통해서 넘긴다.
            SecurityContextHolder.getContext().setAuthentication(authentication);
        }
        // filterChain.doFilter(request, response)를 호출하여 요청 처리를 계속 진행한다.
        filterChain.doFilter(request, response);
	}

}
