package kr.co.alpharking.dao.notice;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;

import kr.co.alpharking.dto.notice.NoticeCreateReq;
import kr.co.alpharking.dto.notice.NoticeFiles;

@Mapper
public interface NoticeDao {
	
	void add(NoticeCreateReq nidto);
	
	void addfile(List<NoticeFiles> nfvo);
	
}
