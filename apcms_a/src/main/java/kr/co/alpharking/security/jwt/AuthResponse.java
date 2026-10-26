package kr.co.alpharking.security.jwt;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class AuthResponse {

	private String access_token;
	private String refresh_token;
	private String token_type;
	private long expires_in;
}
