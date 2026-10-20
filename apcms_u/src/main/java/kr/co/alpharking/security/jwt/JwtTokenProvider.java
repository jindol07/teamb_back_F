package kr.co.alpharking.security.jwt;

import java.security.Key;
import java.time.Instant;
import java.util.Date;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import io.jsonwebtoken.*;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.MalformedJwtException;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.UnsupportedJwtException;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;



@Component
@Slf4j
public class JwtTokenProvider {
	// Key key: JWT 생성 및 검증에 사용되는 비밀 키, HS512 알고리즘으로 생성
	Key key = Keys.secretKeyFor(SignatureAlgorithm.HS512);
	
	// JWT Token을 생성 - 인증된 사용자에게 발급을 함 -> 클라이언트(React) 
	public String  createToken(Authentication authentication) {
		
		UserDetails userDetails = (UserDetails) authentication.getPrincipal();
		Date now = new Date();
		
		//JWT가 발급 되고 나서 약 1시간(3600000 밀리초) 동안 만료 시간을 설정 
		Date expiryDate = new Date(now.getTime() + 3600000);
		
		//Role 가져오기------------------------------------
		String role = authentication.getAuthorities().stream()
				.map(GrantedAuthority::getAuthority)
				.findFirst()
				.orElse("OFFICE");// 기본 Role 설정
		
		 System.out.println("UserDetails =>"+userDetails.getUsername() +",Role => "+role);
		//---------------------------------------------------------------------------------
		String jwtReslut = Jwts.builder()
			   .setSubject(userDetails.getUsername())
			   //-------------------------------------------------
			   .claim("role", role)
			   //-------------------------------------------------
			   .setIssuedAt(new Date()) // 토큰을 발급 한 시점을 이 메서드가 실행되는 시점으로 설정
			   .setExpiration(expiryDate)// 토큰 만료시간
			   .signWith(key, SignatureAlgorithm.HS512)//서명 추가, 비밀키와 해싱 알고리즘을 설정 
			   .compact();//JWT를 문자열로 압축해서 반환 
		
		System.out.println("JwtTokenProvider.jwtReslut:"+jwtReslut);
		return jwtReslut;
		
	}
	  //-------------------------------------------------
	 // 토큰에서 ROLE을 추출해서 반환하는 메서드를 추가한다.
		public String getRole(String token) {
			return Jwts.parserBuilder()
					.setSigningKey(key)
					.build()
					.parseClaimsJws(token)
					.getBody()
					.get("role",String.class);// "role" 클레임에서 Role 값 추출
		}
	
	//------------------------------------------------
	public String resolveToken(HttpServletRequest request) {
        String bearerToken = request.getHeader("Authorization");
        System.out.println("bearerToken:"+bearerToken);
        //반드시 Bearer 시작해야 함.
        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith("Bearer ")) {
            return bearerToken.substring(7);
        }
        return null;
    }
	 // 제공된 JWT 토큰이 유효한지 검증하기 위해서 만든다.
	  
    public boolean validateToken(String token) {
        // Check if the token is valid and not expired
        try {
            // Jwts.parser().setSigningKey(key).parseClaimsJws(token); 라인을 사용하여 토큰의 유효성을 검사
            // Jwts.parser().setSigningKey(key).parseClaimsJws(token); => deprecated
            Jwts.parserBuilder().setSigningKey(key).build().parseClaimsJws(token);
            // 토큰값이 유효하면 true
            return true;
        } catch (MalformedJwtException ex) { // 토큰의 형식이 올바르지 않을 때 발생
            log.error("토큰의 형식이 올바르지 않음 ");
        } catch (ExpiredJwtException ex) {
            log.error("토큰이 만료되었을 때 발생");
        } catch (UnsupportedJwtException ex) {
            log.error("지원되지 않는 토큰 유형일 때 발생");
        } catch (IllegalArgumentException ex) {
            log.error("JWT claims string is empty : 토큰이 비어있거나 null일 때 발생");
        } catch (SignatureException e) {
            log.error("토큰의 서명이 유효하지 않을 때 발생");
        }
        // 토큰이 유효하지 않으면 false
        return false;
    }
    
    /** 주차 웹소켓에서 사용한다. 기존 키로 서명을 검증한 JWT의 만료 시각만 반환한다. */
    public Instant getExpiration(String token) {
        Date expiration = Jwts.parserBuilder().setSigningKey(key).build()
                .parseClaimsJws(token).getBody().getExpiration();
        if (expiration == null) throw new JwtException("JWT 만료 시각이 없습니다.");
        return expiration.toInstant();
    }

 // 목적: 클라이언트로부터 전달받은 JWT를 파싱하고, 토큰의 내용을 추출하기 위해 사용된다.
    public String getUsername(String token) {

        return Jwts.parserBuilder()
                //토큰을 검증할 때 사용할 비밀 키를 설정한다. 서명 검증에 사용되며, 
                // 토큰이 변조되지 않았는지 확인한다.
                .setSigningKey(key)
                //build(): 설정된 파서를 빌드하여 사용할 수 있게 한다.
                .build()
                //parseClaimsJws(token): 전달받은 JWT 토큰을 파싱하여 서명을 검증하고, 토큰의 본문(Claims)을 반환한다.
                .parseClaimsJws(token)
                //getBody().getSubject(): 파싱된 토큰에서 Subject 필드(사용자 이름)를 추출한다.
                .getBody()
                .getSubject();
         //결과: JWT의 Subject(토큰의 소유자 정보)를 추출하여 반환한다.       
    }
}



