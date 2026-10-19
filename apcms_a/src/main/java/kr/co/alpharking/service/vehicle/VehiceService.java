package kr.co.alpharking.service.vehicle;

import java.io.InputStream;
import java.math.BigDecimal;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.ss.usermodel.FormulaEvaluator;

import kr.co.alpharking.dao.vehicle.VehiceDao;
import kr.co.alpharking.dto.vehicle.VehicleDTO;
import kr.co.alpharking.dto.vehicle.VehicleExcelUploadResultDTO;

@Service
@Transactional
public class VehiceService {

    private final VehiceDao vehiceDao;

    public VehiceService(VehiceDao vehiceDao) {
        this.vehiceDao = vehiceDao;
    }

    // 차량 등록
    public void addVehicle(VehicleDTO vehicle) {
        vehiceDao.add(vehicle);
    }

    // 차량 목록 조회
    @Transactional(readOnly = true)
    public List<VehicleDTO> getVehicleList() {
        return vehiceDao.list();
    }

    // 차량 수정
    public void updateVehicle(VehicleDTO vehicle) {
        vehiceDao.update(vehicle);
    }

    // 차량 삭제
    public void deleteVehicle(Long vehicleId) {
        vehiceDao.delete(vehicleId);
    }
    // 엑셀 일괄 등록
    public VehicleExcelUploadResultDTO uploadVehiclesExcel(
            MultipartFile file) {

        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("업로드할 엑셀 파일이 없습니다.");
        }

        String filename = file.getOriginalFilename();
        if (filename == null ||
                !(filename.toLowerCase(Locale.ROOT).endsWith(".xlsx")
                || filename.toLowerCase(Locale.ROOT).endsWith(".xls"))) {
            throw new IllegalArgumentException(
                    "xlsx 또는 xls 파일만 업로드할 수 있습니다.");
        }

        VehicleExcelUploadResultDTO result =
                new VehicleExcelUploadResultDTO();

        List<VehicleDTO> validVehicles = new ArrayList<>();

        try (InputStream inputStream = file.getInputStream();
             Workbook workbook = WorkbookFactory.create(inputStream)) {

            if (workbook.getNumberOfSheets() == 0) {
                throw new IllegalArgumentException(
                        "엑셀 파일에 시트가 없습니다.");
            }

            Sheet sheet = workbook.getSheetAt(0);

            if (sheet.getPhysicalNumberOfRows() == 0) {
                throw new IllegalArgumentException(
                        "엑셀 파일에 데이터가 없습니다.");
            }

            DataFormatter formatter =
                    new DataFormatter(Locale.KOREA);

            FormulaEvaluator evaluator =
                    workbook.getCreationHelper()
                            .createFormulaEvaluator();

            // 첫 번째 행에서 헤더를 읽는다.
            Row headerRow = sheet.getRow(0);

            if (headerRow == null) {
                throw new IllegalArgumentException(
                        "첫 번째 행에 헤더가 필요합니다.");
            }

            Map<String, Integer> headers =
                    readHeaders(headerRow, formatter, evaluator);

            String[] requiredHeaders = {
                "officeid",
                "vehiclenumber",
                "vehiclemodel",
                "ownername",
                "vehicletypecode",
                "registrationtypecode"
            };

            for (String header : requiredHeaders) {
                if (!headers.containsKey(header)) {
                    throw new IllegalArgumentException(
                            "필수 헤더가 없습니다: " + header);
                }
            }

            // 실제 시트의 행 번호를 기준으로 처리한다.
            for (int i = 1; i <= sheet.getLastRowNum(); i++) {
                Row row = sheet.getRow(i);

                if (row == null || isBlankRow(row, formatter, evaluator)) {
                    continue;
                }

                result.setTotalCount(result.getTotalCount() + 1);

                int excelRowNumber = i + 1;

                try {
                    VehicleDTO vehicle = parseVehicle(
                            row, headers, formatter, evaluator);

                    validVehicles.add(vehicle);

                } catch (IllegalArgumentException e) {
                    result.getErrors().add(
                            excelRowNumber + "행: " + e.getMessage());
                }
            }

        } catch (IllegalArgumentException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalArgumentException(
                    "엑셀 파일을 읽을 수 없습니다. 파일 형식과 내용을 확인해 주세요.",
                    e);
        }

        // 검증이 끝난 정상 행만 저장한다.
        // DB 저장 중 예외가 발생하면 트랜잭션 전체가 롤백된다.
        for (VehicleDTO vehicle : validVehicles) {
            vehiceDao.add(vehicle);
        }

        result.setSuccessCount(validVehicles.size());
        result.setFailureCount(
                result.getTotalCount() - result.getSuccessCount());

        return result;
    }

    private Map<String, Integer> readHeaders(
            Row headerRow,
            DataFormatter formatter,
            FormulaEvaluator evaluator) {

        Map<String, Integer> headers = new HashMap<>();

        for (Cell cell : headerRow) {
            String header = formatter
                    .formatCellValue(cell, evaluator)
                    .trim()
                    .toLowerCase(Locale.ROOT);

            if (!header.isEmpty()) {
                headers.put(header, cell.getColumnIndex());
            }
        }

        return headers;
    }

    private VehicleDTO parseVehicle(
            Row row,
            Map<String, Integer> headers,
            DataFormatter formatter,
            FormulaEvaluator evaluator) {

        VehicleDTO vehicle = new VehicleDTO();

        String officeId = getCellValue(
                row, headers, "officeid", formatter, evaluator);

        try {
            vehicle.setOfficeid(
                    new BigDecimal(officeId).longValueExact());
        } catch (Exception e) {
            throw new IllegalArgumentException(
                    "officeid는 정수형 숫자여야 합니다.");
        }

        if (vehicle.getOfficeid() <= 0) {
            throw new IllegalArgumentException(
                    "officeid는 1 이상의 숫자여야 합니다.");
        }

        vehicle.setVehiclenumber(getCellValue(
                row, headers, "vehiclenumber", formatter, evaluator));

        vehicle.setVehiclemodel(getCellValue(
                row, headers, "vehiclemodel", formatter, evaluator));

        vehicle.setOwnername(getCellValue(
                row, headers, "ownername", formatter, evaluator));

        vehicle.setVehicletypecode(getCellValue(
                row, headers, "vehicletypecode", formatter, evaluator)
                .toUpperCase(Locale.ROOT));

        vehicle.setRegistrationtypecode(getCellValue(
                row, headers, "registrationtypecode",
                formatter, evaluator).toUpperCase(Locale.ROOT));

        requireText(vehicle.getVehiclenumber(), "vehiclenumber");
        requireText(vehicle.getVehiclemodel(), "vehiclemodel");
        requireText(vehicle.getOwnername(), "ownername");

        if (!"PERSONAL".equals(vehicle.getVehicletypecode())
                && !"OFFICE".equals(vehicle.getVehicletypecode())) {
            throw new IllegalArgumentException(
                    "vehicletypecode는 PERSONAL 또는 OFFICE여야 합니다.");
        }

        if (!"INITIAL".equals(vehicle.getRegistrationtypecode())
                && !"ADDITIONAL".equals(
                        vehicle.getRegistrationtypecode())) {
            throw new IllegalArgumentException(
                    "registrationtypecode는 INITIAL 또는 ADDITIONAL이어야 합니다.");
        }

        // 관리자가 직접 등록하는 차량
        vehicle.setRegistrationstatuscode("REGISTERED");
        vehicle.setRegisteredat(
                new SimpleDateFormat("yyyy-MM-dd HH:mm:ss")
                        .format(new Date()));
        vehicle.setRejectedreason(null);

        return vehicle;
    }

    private String getCellValue(
            Row row,
            Map<String, Integer> headers,
            String header,
            DataFormatter formatter,
            FormulaEvaluator evaluator) {

        Integer columnIndex = headers.get(header);

        if (columnIndex == null) {
            throw new IllegalArgumentException(
                    "필수 헤더가 없습니다: " + header);
        }

        Cell cell = row.getCell(
                columnIndex, Row.MissingCellPolicy.RETURN_BLANK_AS_NULL);

        if (cell == null) {
            return "";
        }

        return formatter.formatCellValue(cell, evaluator).trim();
    }

    private void requireText(String value, String fieldName) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(
                    fieldName + " 값이 비어 있습니다.");
        }
    }

    private boolean isBlankRow(
            Row row,
            DataFormatter formatter,
            FormulaEvaluator evaluator) {

        for (Cell cell : row) {
            if (!formatter.formatCellValue(cell, evaluator)
                    .trim().isEmpty()) {
                return false;
            }
        }

        return true;
    }
}