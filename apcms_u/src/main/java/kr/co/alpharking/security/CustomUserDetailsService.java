package kr.co.alpharking.security;

import org.springframework.beans.factory.annotation.Autowired;
//import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

@Service
public class CustomUserDetailsService implements UserDetailsService{
	@Autowired
	private UserRepository userRepository;

	@Override
	public UserDetails loadUserByUsername(String username)
	        throws UsernameNotFoundException {

	    System.out.println("1. 조회 시작: " + username);

	    var result = userRepository.findByUsername(username);

	    System.out.println("2. 사용자 존재 여부: " + result.isPresent());

	    UserDetails user = result.orElseThrow(() ->
	        new UsernameNotFoundException(
	            "사용자를 찾을 수 없습니다: " + username
	        )
	    );

	    System.out.println("3. 객체 타입: " + user.getClass().getName());
	    System.out.println("4. 사용자 ID: " + user.getUsername());

	    // 비밀번호 해시 자체는 출력하지 않습니다.
	    System.out.println(
	        "5. 비밀번호 필드 존재 여부: " +
	        (user.getPassword() != null && !user.getPassword().isBlank())
	    );

	    return user;
	}

}
