package kr.co.alpharking.auth;

import java.security.SecureRandom;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.MailException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;

import kr.co.alpharking.dao.auth.EmailVerificationRedisDao;
import kr.co.alpharking.dto.auth.EmailVerificationResponse;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class EmailVerificationService {

    private static final int MAX_ATTEMPTS = 3;
    private static final SecureRandom RANDOM = new SecureRandom();

    private final JavaMailSender mailSender;
    private final EmailVerificationRedisDao redisDao;

    @Value("${spring.mail.username}")
    private String senderAddress;

    public EmailVerificationResponse sendCode(String email) {
        String code = createCode();

        redisDao.saveCode(email, code);

        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(senderAddress);
        message.setTo(email);
        message.setSubject("이메일 인증 코드");
        message.setText("인증 코드는 " + code + " 입니다.");

        try {
            mailSender.send(message);
        } catch (MailException exception) {
            redisDao.deleteCodeAndAttempts(email);
            throw exception;
        }

        return new EmailVerificationResponse(true, "sent");
    }

    public EmailVerificationResponse verifyCode(String email, String inputCode) {
        if (!redisDao.hasCode(email)) {
            return new EmailVerificationResponse(false, "expired");
        }

        if (redisDao.getAttemptCount(email) >= MAX_ATTEMPTS) {
            return new EmailVerificationResponse(false, "exceeded");
        }

        String savedCode = redisDao.getCode(email);

        if (savedCode != null && savedCode.equals(inputCode)) {
            redisDao.markEmailVerified(email);
            redisDao.deleteCodeAndAttempts(email);

            return new EmailVerificationResponse(true, "ok");
        }

        redisDao.increaseAttemptCount(email);
        return new EmailVerificationResponse(false, "wrong");
    }

    public boolean isEmailVerified(String email) {
        return redisDao.isEmailVerified(email);
    }

    public void consumeEmailVerified(String email) {
        redisDao.consumeEmailVerified(email);
    }

    private String createCode() {
        int number = RANDOM.nextInt(1_000_000);
        return String.format("%06d", number);
    }
}