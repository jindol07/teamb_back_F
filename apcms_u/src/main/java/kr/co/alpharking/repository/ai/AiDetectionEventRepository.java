package kr.co.alpharking.repository.ai;

import org.springframework.data.jpa.repository.JpaRepository;

import kr.co.alpharking.entity.ai.AiDetectionEvent;

public interface AiDetectionEventRepository
		extends JpaRepository<AiDetectionEvent, Long> {

}