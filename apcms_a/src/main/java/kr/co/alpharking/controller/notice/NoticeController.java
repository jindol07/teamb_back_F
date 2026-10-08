package kr.co.alpharking.controller.notice;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import jakarta.servlet.http.HttpServletRequest;
import kr.co.alpharking.cmn.page.PagingService;
import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.dto.notice.NoticeFiles;
import kr.co.alpharking.service.notice.NoticeService;

@RestController
@RequestMapping("/api/notice")
public class NoticeController {
	@Autowired
	private NoticeService noticeService;
	
	@Autowired
	private PagingService pagingService;
	
	@Value("${spring.servlet.multipart.location}")
	private String filePath;
	
	@PostMapping("/add")
	public ResponseEntity<?> addNotice(NoticeCreateReq galleryVO,
			@RequestParam("files") MultipartFile[] images, HttpServletRequest request
			) {
		//galleryVO.setReip(request.getRemoteAddr()); // 작성자 IP 저장
		//이미지들을 저장해서 MyBatis로 보내기 위해서 생성 
		List<NoticeFiles> imageList = new ArrayList<>();
		
		for(MultipartFile file : images) {
			if(!file.isEmpty()) {
				String originalFilename = file.getOriginalFilename();
				//File f = new File(filePath+"/notice/",originalFilename);
				//1007
				Path uploadDir = Paths.get(filePath)
				        .toAbsolutePath()
				        .normalize();
				// 저장할 파일 경로 생성
		        Path savePath = uploadDir.resolve(originalFilename);
		        System.out.println("파일 저장 위치 : " + savePath);
		        if (!Files.exists(uploadDir)) {
				    try {
				        Files.createDirectories(uploadDir);
				    } catch (IOException e) {
				        e.printStackTrace();
				    }
				}
		        
				try {
					file.transferTo(savePath);//업로드 완료
					NoticeFiles imageVO = new NoticeFiles();//이미지 객체 생성
					imageVO.setOriginalName(originalFilename); //이미지들의 이름을 vo저장
					imageList.add(imageVO); //책꽃에 저장 
				} catch (IllegalStateException | IOException e) {
					e.printStackTrace();
				}
			}
		}//for 
		// GalleryVO에 이미지 리스트 설정
		galleryVO.setGetfilelist(imageList);
		// service에 등록 
		try {
			noticeService.transcationProcess(galleryVO, imageList);
			System.out.println("transaction success!!");
		} catch (Exception e) {
			e.printStackTrace();
			System.out.println("Rollback!");
			return ResponseEntity.ok("공지사항 등록(파일포함) 실패...");
		}
		return ResponseEntity.ok("공지사항 등록(파일포함) 성공!");
	}

}
