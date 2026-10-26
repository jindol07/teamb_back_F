package kr.co.alpharking;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@SpringBootApplication
public class ApcmsUApplication {

	public static void main(String[] args) {
		SpringApplication.run(ApcmsUApplication.class, args);
	}
	
	// spring boot에서 비동기식 외부 접속[Cros Allow Origin]을 허용해주기 위한 설정
	// 빈으로 등록 - 스프링 컨테이너가 관리할 객체 <bean ~
//	@Bean
//	public WebMvcConfigurer crosConfigurer() {
//		return new WebMvcConfigurer() {
//			@Override
//			public void addCorsMappings(CorsRegistry registry) {
//				System.out.println("Cros Allow Origin 실행!");
//				registry.addMapping("/**")
//						.allowedOrigins("http://192.168.0.39:3001", "http://192.168.0.39:3000", "http://localhost:3001",
//								"http://localhost:3000")
//						// withCredentials: true
//						// backend에서도 .allowCredentials(true) 를 설정해야 함.(세션을 사용해서 동기화 할때 사용 )
//						.allowCredentials(true).allowedHeaders("*").allowedMethods("*").maxAge(3600);
//			}
//		};
//	}

}