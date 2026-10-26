package kr.co.alpharking.auth;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

import kr.co.alpharking.security.Office;
import kr.co.alpharking.security.UserRepository;
import kr.co.alpharking.security.jwt.AuthResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * 네이버 OAuth2 로그인 (회원가입 없이 기존 회원만 로그인).
 *
 * 흐름: 프론트가 {@link #createAuthorizeUrl()}이 만든 주소로 이동 → 네이버가
 * 프론트 콜백 페이지로 1회용 code 전달 → 프론트가 code/state를
 * /api/auth/naver/login 으로 전달 → 이 서비스가 프로필을 조회해 기존 회원을
 * 찾고, 일반 로그인과 동일한 access/refresh 토큰을 발급한다.
 *
 * 기존 회원 매칭:
 * 1. OFFICE.NAVER_USER_ID (이미 연동된 네이버 ID)
 * 2. OFFICE.EMAIL == 네이버 이메일 (UK_OFFICE_EMAIL 유니크)
 *    이 경우 NAVER_USER_ID 를 저장해 두어 다음 로그인부터는 이메일에 의존하지 않는다.
 *    (기존 KAKAO_USER_ID 컬럼과 같은 방식)
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class NaverOAuthService {

    private static final String AUTHORIZE_ENDPOINT = "https://nid.naver.com/oauth2.0/authorize";
    private static final String TOKEN_ENDPOINT = "https://nid.naver.com/oauth2.0/token";
    private static final String PROFILE_ENDPOINT = "https://openapi.naver.com/v1/nid/me";

    private static final String STATE_KEY_PREFIX = "auth:naver:state:";
    private static final Duration STATE_TTL = Duration.ofMinutes(5);

    private static final ParameterizedTypeReference<Map<String, Object>> JSON_OBJECT =
            new ParameterizedTypeReference<>() {
            };

    private final UserRepository userRepository;
    private final AuthTokenService authTokenService;
    private final StringRedisTemplate redisTemplate;

    private final RestClient restClient = RestClient.create();

    @Value("${app.naver.client-id}")
    private String clientId;

    @Value("${app.naver.client-secret}")
    private String clientSecret;

    @Value("${app.naver.redirect-uri}")
    private String redirectUri;

    @Value("${app.auth.office-active-status}")
    private String officeActiveStatus;

    /** 네이버 authorize URL을 만들고, 1회용 state를 Redis에 5분간 보관한다. */
    public String createAuthorizeUrl() {
        requireConfiguration();

        String state = UUID.randomUUID().toString().replace("-", "");
        redisTemplate.opsForValue().set(STATE_KEY_PREFIX + state, "1", STATE_TTL);

        return AUTHORIZE_ENDPOINT
                + "?response_type=code"
                + "&client_id=" + encode(clientId)
                + "&redirect_uri=" + encode(redirectUri)
                + "&state=" + encode(state);
    }

    /** 콜백의 code/state를 검증하고 네이버 프로필로 기존 회원을 찾아 토큰을 발급한다. */
    public AuthResponse login(String code, String state) {
        if (!StringUtils.hasText(code)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "인증 코드가 없습니다.");
        }

        requireConfiguration();

        if (!consumeState(state)) {
            throw new ResponseStatusException(
                    HttpStatus.UNAUTHORIZED, "네이버 로그인 요청이 만료되었습니다. 다시 시도해주세요.");
        }

        Map<String, Object> tokenResponse = requestToken(code, state);
        String naverAccessToken = textOrNull(tokenResponse, "access_token");
        if (!StringUtils.hasText(naverAccessToken)) {
            log.warn("[NAVER] 토큰 교환 실패: error={}, description={}",
                    textOrNull(tokenResponse, "error"),
                    textOrNull(tokenResponse, "error_description"));
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY, "네이버 인증에 실패했습니다. 잠시 후 다시 시도해주세요.");
        }

        Map<String, Object> profile = requestProfile(naverAccessToken);
        Map<String, Object> naverUser = mapOrNull(profile, "response");
        String naverUserId = textOrNull(naverUser, "id");
        String naverEmail = textOrNull(naverUser, "email");

        if (!"00".equals(textOrNull(profile, "resultcode")) || !StringUtils.hasText(naverUserId)) {
            log.warn("[NAVER] 프로필 조회 실패: resultcode={}, message={}",
                    textOrNull(profile, "resultcode"),
                    textOrNull(profile, "message"));
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY, "네이버 회원 정보를 가져오지 못했습니다.");
        }

        Office office = resolveOffice(naverUserId, naverEmail);

        if (!StringUtils.hasText(office.getStatus_code())
                || !officeActiveStatus.equals(office.getStatus_code())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "사용할 수 없는 계정입니다.");
        }

        Authentication authentication =
                new UsernamePasswordAuthenticationToken(office, null, office.getAuthorities());

        return authTokenService.issue(authentication);
    }

    private Office resolveOffice(String naverUserId, String naverEmail) {
        Optional<Office> linked = userRepository.findByNaverUserId(naverUserId);
        if (linked.isPresent()) {
            return linked.get();
        }

        if (StringUtils.hasText(naverEmail)) {
            List<Office> matches = userRepository.findByEmailIgnoreCase(naverEmail.trim());

            if (matches.size() == 1) {
                Office office = matches.get(0);

                if (StringUtils.hasText(office.getNaver_user_id())) {
                    log.warn("[NAVER] 이미 다른 네이버 계정과 연결된 회원입니다. office_id={}",
                            office.getOffice_id());
                    throw new ResponseStatusException(
                            HttpStatus.UNAUTHORIZED,
                            "이미 다른 네이버 계정과 연결된 회원입니다. 관리자에게 문의해주세요.");
                }

                office.setNaver_user_id(naverUserId);
                userRepository.save(office);
                log.info("[NAVER] 최초 로그인으로 계정 연결: office_id={}", office.getOffice_id());
                return office;
            }

            if (matches.size() > 1) {
                log.warn("[NAVER] 동일 이메일 회원이 여러 명이라 자동 연결할 수 없습니다. email={}, count={}",
                        naverEmail, matches.size());
            }
        }

        log.warn("[NAVER] 연결된 회원 없음: naver_user_id={}, email={}", naverUserId, naverEmail);
        throw new ResponseStatusException(
                HttpStatus.UNAUTHORIZED, "네이버 계정과 연결된 회원 정보가 없습니다. 관리자에게 문의해주세요.");
    }

    private Map<String, Object> requestToken(String code, String state) {
        LinkedMultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type", "authorization_code");
        form.add("client_id", clientId);
        form.add("client_secret", clientSecret);
        form.add("code", code);
        form.add("state", state);

        try {
            Map<String, Object> body = restClient.post()
                    .uri(TOKEN_ENDPOINT)
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(form)
                    .retrieve()
                    .body(JSON_OBJECT);

            if (body == null) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY, "네이버 인증에 실패했습니다. 잠시 후 다시 시도해주세요.");
            }
            return body;
        } catch (RestClientResponseException e) {
            log.warn("[NAVER] 토큰 요청 HTTP 오류: status={}, body={}",
                    e.getStatusCode(), e.getResponseBodyAsString());
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY, "네이버 인증에 실패했습니다. 잠시 후 다시 시도해주세요.");
        } catch (RestClientException e) {
            log.warn("[NAVER] 토큰 요청 실패: {}", e.getMessage());
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY, "네이버 인증 서버에 연결할 수 없습니다.");
        }
    }

    private Map<String, Object> requestProfile(String naverAccessToken) {
        try {
            Map<String, Object> body = restClient.get()
                    .uri(PROFILE_ENDPOINT)
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + naverAccessToken)
                    .accept(MediaType.APPLICATION_JSON)
                    .retrieve()
                    .body(JSON_OBJECT);

            if (body == null) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY, "네이버 회원 정보를 가져오지 못했습니다.");
            }
            return body;
        } catch (RestClientResponseException e) {
            log.warn("[NAVER] 프로필 요청 HTTP 오류: status={}, body={}",
                    e.getStatusCode(), e.getResponseBodyAsString());
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY, "네이버 회원 정보를 가져오지 못했습니다.");
        } catch (RestClientException e) {
            log.warn("[NAVER] 프로필 요청 실패: {}", e.getMessage());
            throw new ResponseStatusException(
                    HttpStatus.BAD_GATEWAY, "네이버 인증 서버에 연결할 수 없습니다.");
        }
    }

    private boolean consumeState(String state) {
        if (!StringUtils.hasText(state)) {
            return false;
        }
        return Boolean.TRUE.equals(redisTemplate.delete(STATE_KEY_PREFIX + state));
    }

    private void requireConfiguration() {
        if (!StringUtils.hasText(clientId)
                || !StringUtils.hasText(clientSecret)
                || !StringUtils.hasText(redirectUri)) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "네이버 로그인 설정(NAVER_CLIENT_ID/NAVER_CLIENT_SECRET/NAVER_REDIRECT_URI)이 없습니다.");
        }
    }

    private String textOrNull(Map<String, Object> map, String key) {
        if (map == null) {
            return null;
        }
        Object value = map.get(key);
        return value == null ? null : String.valueOf(value);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> mapOrNull(Map<String, Object> map, String key) {
        if (map == null) {
            return null;
        }
        Object value = map.get(key);
        return value instanceof Map<?, ?> nested ? (Map<String, Object>) nested : null;
    }

    private String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
