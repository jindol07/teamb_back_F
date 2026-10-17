package kr.co.alpharking.dto.vehicle;

import java.util.ArrayList;
import java.util.List;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class VehicleExcelUploadResultDTO {
	
	private int totalCount;
	private int successCount;
	private int failureCount;
	private List<String> errors = new ArrayList<>();
}
