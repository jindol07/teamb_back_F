package kr.co.alpharking.entity.cmn;

import jakarta.persistence.Column;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.Immutable;

@Entity(name = "MyPageCommonCodeDetail")
@Table(name = "COMMON_CODE_DETAIL")
@Immutable
@Getter
@NoArgsConstructor
public class CommonCodeDetail {
    @EmbeddedId
    private CommonCodeKey id;
    @Column(name = "CODE_NAME", length = 100)
    private String codeName;
}
