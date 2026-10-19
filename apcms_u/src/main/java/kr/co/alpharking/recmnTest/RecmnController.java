package kr.co.alpharking.recmnTest;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/recmn")
public class RecmnController {
	@Autowired
	private RecmnService recmnService;
	
	@GetMapping("/{officeId}")
    public List<PrkPastHisRes> getPrkPastHisById(
            @PathVariable("officeId") Long officeId) {

        return recmnService.getPrkPastHisById(officeId);
    }
	
}

