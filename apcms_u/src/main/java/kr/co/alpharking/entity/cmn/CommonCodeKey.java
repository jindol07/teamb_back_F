package kr.co.alpharking.entity.cmn;

import java.io.Serializable;
import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import lombok.Data;
import lombok.NoArgsConstructor;

@Embeddable
@Data
@NoArgsConstructor
public class CommonCodeKey implements Serializable {
    @Column(name = "GROUP_CODE", length = 50)
    private String groupCode;
    @Column(name = "CODE", length = 50)
    private String code;
}
