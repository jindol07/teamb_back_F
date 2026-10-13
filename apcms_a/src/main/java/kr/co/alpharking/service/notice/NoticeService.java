
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

        // 1. 공지사항 등록
        noticeDao.add(nidto);

        // 2. 첨부파일이 있을 경우에만 실행
        if (nfvo != null && !nfvo.isEmpty()) {

            // 3. 등록된 공지사항 번호 가져오기
            Integer noticeId = nidto.getNoticeId();

            // 4. 각 첨부파일에 번호 설정
            for (NoticeFiles file : nfvo) {

                // 공지사항 번호 설정
                file.setNoticeId(noticeId);

                // 첨부파일 고유번호 생성
                file.setNoticeAttachmentId(
                    noticeDao.nextAttachmentId()
                );
            }

            // 5. 첨부파일 목록 DB 등록
            noticeDao.addfile(nfvo);
        }
    }
}
