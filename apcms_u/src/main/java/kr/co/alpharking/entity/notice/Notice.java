package kr.co.alpharking.entity.notice;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Lob;
import jakarta.persistence.OneToMany;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Getter
@Setter
@NoArgsConstructor
@Table(name = "NOTICE")
public class Notice {
	@Id
	@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "seq_notice_gen")
	@SequenceGenerator(name = "seq_notice_gen", sequenceName = "seq_notice", allocationSize = 1)
	private Integer noticeId;
	@Column(length = 19, nullable = false)
	private Integer writerAdminId;
	@Column(length = 50, nullable = false)
	private String noticeTypeCode;
	@Column(length = 100, nullable = false)
	private String title;
	@Lob
	@Column(nullable = false)
	private String content;
	@Column(length = 10, nullable = false)
	private int viewCount;
	@CreationTimestamp
	private LocalDateTime createdAt;
	@UpdateTimestamp
	private LocalDateTime updatedAt;
	
	private LocalDateTime deletedAt;
	
	//1:N 즉 collection관계 
	@OneToMany(mappedBy = "notice", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
	private List<NoticeAttachment> fileList = new ArrayList<>();
	
}
