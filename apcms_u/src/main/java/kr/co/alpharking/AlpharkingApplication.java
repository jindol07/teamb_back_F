package kr.co.alpharking;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@SpringBootApplication
public class AlpharkingApplication {

	public static void main(String[] args) {
		SpringApplication.run(AlpharkingApplication.class, args);
	}
	@Bean
	public WebMvcConfigurer corsConfigurer() {
		return new WebMvcConfigurer() {
			@Override
			public void addCorsMappings(CorsRegistry registry) {
				System.out.println("Test==========");
				registry.addMapping("/**")
						.allowedOrigins("http://192.168.0.13:3000", "http://localhost:3000")
						.allowedHeaders("*")
						.allowedMethods("*").maxAge(3600);
			}

		};
	}
}
