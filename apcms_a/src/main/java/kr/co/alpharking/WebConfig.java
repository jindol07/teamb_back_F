package kr.co.alpharking;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer{
	//application.properties에서 값 읽어오기
		//# -v ~/upload:/app/upload  => docker volumn  
		//spring.servlet.multipart.location=/app/upload
		@Value("${spring.servlet.multipart.location}")
		private String uploadPath;
		
		@Override
		public void addResourceHandlers(ResourceHandlerRegistry registry) {
			registry.addResourceHandler("/imgfile/**")
			.addResourceLocations("file:"+uploadPath+"/");
		}
}
