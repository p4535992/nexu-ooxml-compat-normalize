package io.github.p4535992.ooxmlcompatnormalize.quarkus;

import io.quarkus.test.junit.QuarkusIntegrationTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasItems;

@QuarkusIntegrationTest
class NormalizeResourceIT {
    private static final String CONTEXT = "/ooxml-compat-normalize";

    @Test
    void infoEndpointIsAvailableUnderConfiguredContextPath() {
        // Integration tests start the packaged JAR and configure the HTTP root path.
        // Keep test paths relative so the configured context is applied exactly once.
        given()
                .when().get("/api/info")
                .then()
                .statusCode(200)
                .body("name", equalTo("ooxml-compat-normalize-quarkus"))
                .body("engine", equalTo("java"))
                .body("contextPath", equalTo(CONTEXT))
                .body("formats", hasItems("docx", "xlsx", "pptx"));
    }

    @Test
    void homePageIsAvailableUnderConfiguredContextPath() {
        given()
                .when().get("/")
                .then()
                .statusCode(200)
                .contentType("text/html")
                .body(containsString("OOXML Compat Normalize"))
                .body(containsString("Normalizza e scarica"));
    }
}
