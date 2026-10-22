package kr.co.alpharking.recmnTest;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class RecmnService {

    @Autowired
    private RecmnRepository recmnRepository;

    public List<PrkPastHisRes> getPrkPastHisById(Long officeId) {

        // 1. Repository에서 과거 주차이력 조회
        List<Object[]> rows = recmnRepository.getPrkPastHisById(officeId);

        // 2. 반환할 DTO 리스트 생성
        List<PrkPastHisRes> result = new ArrayList<>();

        // 3. 조회된 주차이력을 한 건씩 DTO로 변환
        for (Object[] row : rows) {

            PrkPastHisRes dto = new PrkPastHisRes();

            // Oracle NUMBER 타입은 Number로 받아 Integer로 변환
            dto.setUsageId(((Number) row[0]).intValue());
            dto.setOfficeId(((Number) row[1]).intValue());

            // TO_CHAR 결과는 문자열로 변환
            dto.setUsageDate((String) row[2]);
            dto.setTargetZone((String) row[3]);

            // 4. DTO 리스트에 추가
            result.add(dto);
        }

        // 5. 변환된 주차이력 리스트 반환
        return result;
    }

    // 주차 이력이 없는 사용자는 예약 가능한 전체 공간 중 무작위 추천
    public ParkingRecommendationResponse recommendRandomParking(
            ParkingRecommendationRequest request
    ) {
        if (request.getStartDate() == null || request.getEndDate() == null) {
            throw new IllegalArgumentException("예약 시작일과 종료일을 선택해 주세요.");
        }
        if (request.getEndDate().isBefore(request.getStartDate())) {
            throw new IllegalArgumentException("종료일은 시작일보다 빠를 수 없습니다.");
        }

        LocalDateTime startAt = request.getStartDate().atStartOfDay();
        LocalDateTime endAt = request.getEndDate()
                .plusDays(1)
                .atStartOfDay()
                .minusNanos(1);
        List<Object[]> availableSpaces =
                recmnRepository.findAvailableSpaces(startAt, endAt);

        if (availableSpaces.isEmpty()) {
            throw new IllegalArgumentException("선택한 기간에 예약 가능한 공간이 없습니다.");
        }

        Object[] selectedSpace = availableSpaces.get(
                ThreadLocalRandom.current().nextInt(availableSpaces.size()));
        return new ParkingRecommendationResponse(
                ((Number) selectedSpace[0]).longValue(),
                ((Number) selectedSpace[1]).intValue(),
                String.valueOf(selectedSpace[2]),
                Integer.parseInt(String.valueOf(selectedSpace[3]).trim())
        );
    }
    // 선택한 기간에 이용 가능한 공간 중 과거 이용이 가장 많았던 층의 공간을 추천
    public ParkingRecommendationResponse recommendParking(
            Long officeId,
            ParkingRecommendationRequest request,
            List<String> recommendedZones
    ) {
        if (request.getStartDate() == null || request.getEndDate() == null) {
            throw new IllegalArgumentException("예약 시작일과 종료일을 선택해 주세요.");
        }

        if (request.getEndDate().isBefore(request.getStartDate())) {
            throw new IllegalArgumentException("종료일은 시작일보다 빠를 수 없습니다.");
        }

        // 시작일 00:00부터 종료일 23:59:59.999999999까지 조회
        LocalDateTime startAt = request.getStartDate().atStartOfDay();
        LocalDateTime endAt = request.getEndDate()
                .plusDays(1)
                .atStartOfDay()
                .minusNanos(1);

        // 선택한 기간에 예약 및 현재 주차 이용이 없는 공간 조회
        List<Object[]> availableSpaces =
                recmnRepository.findAvailableSpaces(startAt, endAt);

        if (availableSpaces.isEmpty()) {
            throw new IllegalArgumentException("선택한 기간에 예약 가능한 공간이 없습니다.");
        }

        if (recommendedZones == null || recommendedZones.isEmpty()) {
            throw new IllegalStateException("AI가 추천 구역을 반환하지 않았습니다.");
        }

        // 사용자별 층 이용 횟수 조회
        List<Object[]> floorUsageCounts =
                recmnRepository.findPastUsageCountByFloor(officeId);

        Integer preferredFloor = null;
        long highestUsageCount = -1;

        // 이용 횟수가 가장 많은 층 선택
        for (Object[] row : floorUsageCounts) {
            Integer floorNo = ((Number) row[0]).intValue();
            long usageCount = ((Number) row[1]).longValue();

            if (usageCount > highestUsageCount) {
                highestUsageCount = usageCount;
                preferredFloor = floorNo;
            }
        }

        List<Object[]> candidates = new ArrayList<>();

        // 선호 층에 빈 공간이 있으면 그 층에서 추천 후보 구성
        if (preferredFloor != null) {
            for (String zoneCode : recommendedZones) {
                for (Object[] row : availableSpaces) {
                    Integer floorNo = ((Number) row[1]).intValue();
                    String availableZone = String.valueOf(row[2]);

                    if (floorNo.equals(preferredFloor) && availableZone.equalsIgnoreCase(zoneCode)) {
                        candidates.add(row);
                    }
                }
                if (!candidates.isEmpty()) {
                    break;
                }
            }
        }

        // 과거 이력이 없거나 선호 층에 빈 공간이 없으면 전체 빈 공간에서 추천
        if (candidates.isEmpty()) {
            for (String zoneCode : recommendedZones) {
                for (Object[] row : availableSpaces) {
                    String availableZone = String.valueOf(row[2]);
                    if (availableZone.equalsIgnoreCase(zoneCode)) {
                        candidates.add(row);
                    }
                }
                if (!candidates.isEmpty()) {
                    break;
                }
            }
        }

        if (candidates.isEmpty()) {
            throw new IllegalStateException("AI 추천 구역에 예약 가능한 공간이 없습니다.");
        }

        // 후보 중 하나를 무작위로 선택
        int randomIndex = ThreadLocalRandom.current().nextInt(candidates.size());
        Object[] selectedSpace = candidates.get(randomIndex);

        return new ParkingRecommendationResponse(
                ((Number) selectedSpace[0]).longValue(),
                ((Number) selectedSpace[1]).intValue(),
                String.valueOf(selectedSpace[2]),
                Integer.parseInt(String.valueOf(selectedSpace[3]).trim())
        );
    }
}
