package kr.co.alpharking.service.vehicle;

import static org.junit.jupiter.api.Assertions.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import kr.co.alpharking.entity.vehicle.Vehicle;

import java.util.Optional;

@SpringBootTest
public class VehicleServiceTest {

	@Autowired
	private VehicleService vehicleService;

	// 1. 등록 승인된 차량 조회
	@Test
	public void testRegisteredVehicle() {

		Optional<Vehicle> vehicle = vehicleService.findRegisteredVehicleByNumber("91소6408");

		assertTrue(vehicle.isPresent());

		assertEquals(1L, vehicle.get().getVehicleId());

		assertEquals("REGISTERED", vehicle.get().getRegistrationStatusCode());

		assertNull(vehicle.get().getDeletedAt());
	}

	// 2. DB에 존재하지 않는 차량 조회
	@Test
	public void testUnregisteredVehicle() {

		Optional<Vehicle> vehicle = vehicleService.findRegisteredVehicleByNumber("56허9082");

		assertTrue(vehicle.isEmpty());
	}

	// 3. 등록 요청 상태인 차량 조회
	@Test
	public void testRequestedVehicle() {

		Optional<Vehicle> vehicle = vehicleService.findRegisteredVehicleByNumber("567다 2345");

		assertTrue(vehicle.isEmpty());
	}

	// 4. 등록 거절 상태인 차량 조회
	@Test
	public void testRejectedVehicle() {

		Optional<Vehicle> vehicle = vehicleService.findRegisteredVehicleByNumber("345다 6789");

		assertTrue(vehicle.isEmpty());
	}
}
