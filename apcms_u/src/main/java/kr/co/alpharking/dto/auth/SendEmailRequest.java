package kr.co.alpharking.dto.auth;

import java.time.LocalDateTime;
import java.util.List;

import kr.co.alpharking.security.SignupVehicle;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class SendEmailRequest {
	private String email;
}
