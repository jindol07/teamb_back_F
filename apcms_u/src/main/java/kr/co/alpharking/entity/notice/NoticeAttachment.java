package kr.co.alpharking.entity.notice;

import java.time.LocalDateTime;

import org.hibernate.annotations.CreationTimestamp;

import com.fasterxml.jackson.annotation.JsonIgnore;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Getter
@Setter
@NoArgsConstructor
@Table(name = "NOTICE_ATTACHMENT")
public class NoticeAttachment {
	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "seq_notice_attachment_gen")
	@SequenceGenerator(name = "seq_notice_attachment_gen", sequenceName = "seq_notice_attachment", allocationSize = 1)
	private Integer noticeAttachmentId;
	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "notice_id", nullable = false)
	@JsonIgnore
	private Notice notice;
	@Column(length = 100)
	private String originalName;
	@Column(length = 100)
	private String storedName;
	@Column(length = 500)
	private String filePath;
	//@Column(length = 19)
	private Long fileSize;
	@CreationTimestamp
	private LocalDateTime createdAt;
}
