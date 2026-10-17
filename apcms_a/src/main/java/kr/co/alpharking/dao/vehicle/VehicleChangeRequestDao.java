package kr.co.alpharking.dao.vehicle;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import kr.co.alpharking.dto.vehicle.VehicleChangeRequestDTO;

@Mapper
public interface VehicleChangeRequestDao {

    // 차량 변경 요청 등록
    void add(VehicleChangeRequestDTO vehicleChangeRequest);

    // 차량 변경 요청 검토 처리 (승인 / 반려)
    void update(VehicleChangeRequestDTO vehicleChangeRequest);
    
    // 차량 요청 목록 조회
    List<VehicleChangeRequestDTO>list();

    // 차량 변경 요청 취소
    void delete(
        @Param("vehicle_change_request_id") Long vehicleChangeRequestId
    );

    // 실제 차량 변경 적용 완료 처리
    void markApplied(
        @Param("vehicle_change_request_id") Long vehicleChangeRequestId
    );
}