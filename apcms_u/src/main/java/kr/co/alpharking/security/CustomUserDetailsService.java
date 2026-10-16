package kr.co.alpharking.security;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;

@Configuration
public class CustomUserDetailsService implements UserDetailsService{
	
	@Autowired
	private UserRepository userRepository;

	@Override
	public UserDetails loadUserByUsername(String username)
	        throws UsernameNotFoundException {

	    return userRepository.findByUsername(username)
	            .orElseThrow(() ->
	                new UsernameNotFoundException(
	                    "사용자를 찾을 수 없습니다: " + username
	                )
	            );
	}

}
