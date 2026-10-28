package kr.co.alpharking.service.mypage;

import static org.junit.jupiter.api.Assertions.*;
import java.util.List;
import java.sql.Types;
import org.hibernate.SessionFactory;
import org.hibernate.boot.MetadataSources;
import org.hibernate.boot.registry.StandardServiceRegistryBuilder;
import org.hibernate.community.dialect.OracleLegacyDialect;
import org.hibernate.dialect.DatabaseVersion;
import org.hibernate.query.spi.Limit;
import org.junit.jupiter.api.Test;
import org.springframework.data.jpa.repository.support.JpaRepositoryFactory;
import kr.co.alpharking.dto.mileage.MileagehistoryDto;
import kr.co.alpharking.entity.mypage.*;
import kr.co.alpharking.entity.cmn.CommonCodeDetail;
import kr.co.alpharking.entity.report.ReportEntity;
import kr.co.alpharking.entity.vehicle.Vehicle;
import kr.co.alpharking.recmnTest.PrkUsage;
import kr.co.alpharking.repository.mypage.*;
import kr.co.alpharking.security.Office;
import kr.co.alpharking.security.Company;

/** DB 접속·DDL 없이 실제 Hibernate 메타데이터와 Spring Data로 조회문을 검증한다. */
class MyPageJpaQueryTest {
    @Test
    // DB 접속 없이 JPA 매핑과 Repository의 복합 공통코드 조인 조회문을 검증한다.
    void allRepositoryQueriesAndCompositeCodeJoinsValidateWithoutDatabase() {
        var registry = new StandardServiceRegistryBuilder()
                .applySetting("hibernate.dialect", OracleLegacyDialect.class.getName())
                .applySetting("hibernate.boot.allow_jdbc_metadata_access", false)
                .applySetting("hibernate.hbm2ddl.auto", "none")
                .applySetting("hibernate.connection.provider_class",
                        "org.hibernate.engine.jdbc.connections.internal.UserSuppliedConnectionProviderImpl")
                .build();
        try {
            var sources = new MetadataSources(registry);
            List.of(Office.class, Company.class, MileagehistoryDto.class, PrkUsage.class, Vehicle.class, ReportEntity.class,
                    OfficeCharge.class, OfficeChargeItem.class, VehiclePenalty.class, CommonCodeDetail.class)
                    .forEach(sources::addAnnotatedClass);
            var metadata = sources.buildMetadata();
            try (SessionFactory factory = metadata.buildSessionFactory();
                    var em = factory.createEntityManager()) {
                // 실제 Oracle REASON 컬럼과 동일하게 CLOB으로 매핑되는지 검증한다.
                var reasonType = (org.hibernate.type.BasicType<?>) metadata.getEntityBinding(VehiclePenalty.class.getName())
                        .getProperty("reason").getType();
                assertEquals(Types.CLOB, reasonType.getJdbcType().getJdbcTypeCode());
                var repositories = new JpaRepositoryFactory(em);
                assertNotNull(repositories.getRepository(MyPageOfficeRepository.class));
                assertNotNull(repositories.getRepository(MyPageCompanyRepository.class));
                assertNotNull(repositories.getRepository(OfficeChargeRepository.class));
                assertNotNull(repositories.getRepository(OfficeChargeItemRepository.class));
                assertNotNull(repositories.getRepository(MyPageMileageRepository.class));
                assertNotNull(repositories.getRepository(MyPageParkingUsageRepository.class));
                assertNotNull(repositories.getRepository(MyPageReportRepository.class));
                assertNotNull(repositories.getRepository(MyPagePenaltyRepository.class));
            }
        } finally {
            StandardServiceRegistryBuilder.destroy(registry);
        }
    }

    @Test
    // Oracle 11g 페이징 SQL이 OFFSET 대신 ROWNUM을 사용하는지 검증한다.
    void oracle11PaginationUsesRownumInsteadOfOffsetFetch() {
        var dialect = new OracleLegacyDialect(DatabaseVersion.make(11, 2));
        var limit = new Limit();
        limit.setFirstRow(10); limit.setMaxRows(10);
        String sql = dialect.getLimitHandler().processSql(
                "select PARKING_USAGE_ID from PARKING_USAGE order by ENTRY_AT desc, PARKING_USAGE_ID desc", limit);
        assertTrue(sql.toLowerCase().contains("rownum"));
        assertFalse(sql.toLowerCase().contains("fetch first"));
        assertFalse(sql.toLowerCase().contains("offset"));
    }
}
