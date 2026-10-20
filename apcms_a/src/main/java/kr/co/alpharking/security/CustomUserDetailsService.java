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
	    var result = userRepository.findByUsername(username);

	    UserDetails user = result.orElseThrow(() ->
	        new UsernameNotFoundException(
	            "사용자를 찾을 수 없습니다: " + username
	        )
	    );

	    return user;
	}
}
