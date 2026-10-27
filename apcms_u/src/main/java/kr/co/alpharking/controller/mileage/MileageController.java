package kr.co.alpharking.controller.mileage;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import kr.co.alpharking.dto.mileage.MileagehistoryDto;
import kr.co.alpharking.service.mileage.MileagehistoryService;
import kr.co.alpharking.security.Office;

@RestController
@RequestMapping("/api/mileage/history")
public class MileageController {

    private final MileagehistoryService mileagehistoryService;

    public MileageController(MileagehistoryService mileagehistoryService) {
        this.mileagehistoryService = mileagehistoryService;
    }

    @GetMapping
    public List<MileagehistoryDto> findAll(@AuthenticationPrincipal Office office) {
        return mileagehistoryService.findAll(office.getOffice_id());
    }

    @GetMapping("/{id}")
    public MileagehistoryDto findById(@PathVariable("id") Long id) {
        return mileagehistoryService.findById(id);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public MileagehistoryDto create(@RequestBody MileagehistoryDto mileagehistory) {
        return mileagehistoryService.create(mileagehistory);
    }

    @PutMapping("/{id}")
    public MileagehistoryDto update(@PathVariable("id") Long id, @RequestBody MileagehistoryDto mileagehistory) {
        return mileagehistoryService.update(id, mileagehistory);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable("id") Long id) {
        mileagehistoryService.delete(id);
    }
}
