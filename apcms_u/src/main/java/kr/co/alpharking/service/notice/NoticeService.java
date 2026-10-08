package kr.co.alpharking.service.notice;

import java.util.List;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import kr.co.alpharking.dto.notice.NoticeRes;
//import kr.co.alpharking.entity.notice.Notice;
import kr.co.alpharking.repository.notice.NoticeRepository;

@Service
public class NoticeService {
	@Autowired
	private NoticeRepository noticeRepository;
	
	public List<NoticeRes> getAllNotices() {
		 return noticeRepository.findAllByOrderByNoticeIdDesc()
				 .stream().map(NoticeRes::from) // Entity -> NoticeRes 매핑
				 .collect(Collectors.toList());
    }
	
}
