package kr.co.alpharking.auth;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.mail.MailException;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.auth.EmailVerificationResponse;
import kr.co.alpharking.dto.auth.SendEmailRequest;
import kr.co.alpharking.dto.auth.VerifyEmailRequest;
import lombok.RequiredArgsConstructor;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/auth/email")
public class EmailVerificationController {

    private final EmailVerificationService emailVerificationService;

    @PostMapping("/send")
    public ResponseEntity<EmailVerificationResponse> sendCode(
            @RequestBody(required = false) SendEmailRequest request) {
        if (request == null || request.getEmail() == null || request.getEmail().isBlank()) {
            return ResponseEntity.badRequest()
                    .body(new EmailVerificationResponse(false, "invalid_email"));
        }

        try {
            return ResponseEntity.ok(emailVerificationService.sendCode(request.getEmail().trim()));
        } catch (MailException exception) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(new EmailVerificationResponse(false, "send_failed"));
        }
    }

    @PostMapping("/verify")
    public ResponseEntity<EmailVerificationResponse> verifyCode(
            @RequestBody(required = false) VerifyEmailRequest request) {
        if (request == null
                || request.getEmail() == null || request.getEmail().isBlank()
                || request.getCode() == null || request.getCode().isBlank()) {
            return ResponseEntity.badRequest()
                    .body(new EmailVerificationResponse(false, "invalid_request"));
        }

        return ResponseEntity.ok(emailVerificationService.verifyCode(
                request.getEmail().trim(), request.getCode().trim()));
    }
}
