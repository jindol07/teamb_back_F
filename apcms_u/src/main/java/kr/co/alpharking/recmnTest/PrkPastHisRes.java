package kr.co.alpharking.recmnTest;

import java.util.Date;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Data
@Builder
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class PrkPastHisRes {
	private Integer officeId;
    private Integer usageId;
    private String usageDate;
    private String targetZone;
}
