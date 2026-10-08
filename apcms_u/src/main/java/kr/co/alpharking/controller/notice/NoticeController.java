package kr.co.alpharking.controller.notice;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;

import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.notice.NoticeRes;
//import kr.co.alpharking.entity.notice.Notice;
import kr.co.alpharking.service.notice.NoticeService;

@RestController
@RequestMapping("/api/notice")
public class NoticeController {
	@Autowired
	private NoticeService noticeService;
	
	private final Path uploadDir = Paths.get("uploads").toAbsolutePath().normalize();
	
	public NoticeController() {
        try {
            Files.createDirectories(uploadDir);
        } catch (IOException e) {
            throw new RuntimeException("Failed to create upload directory.", e);
        }
    }
	
	@GetMapping
	public ResponseEntity<List<NoticeRes>> getAllNotices() {
        List<NoticeRes> nList = noticeService.getAllNotices();
        return ResponseEntity.ok(nList);
    }

}
