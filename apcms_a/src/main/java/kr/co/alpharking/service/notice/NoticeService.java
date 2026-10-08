package kr.co.alpharking.service.notice;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import kr.co.alpharking.dao.notice.NoticeDao;
import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.dto.notice.NoticeFiles;

@Service
public class NoticeService {
	@Autowired
	private NoticeDao noticeDao;
	
	@Transactional
	public void transcationProcess(NoticeCreateReq nidto, List<NoticeFiles> nfvo) {
		noticeDao.add(nidto);
		noticeDao.addfile(nfvo);
	}
}
