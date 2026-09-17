package io.github.p4535992.ooxmlcompatnormalize.quarkus;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasItems;

@QuarkusTest
class NormalizeResourceTest {
    private static final String CONTEXT = "/ooxml-compat-normalize";

    @Test
    void infoEndpointIsAvailableUnderContextPath() {
        given()
                .when().get(CONTEXT + "/api/info")
                .then()
                .statusCode(200)
                .body("name", equalTo("ooxml-compat-normalize-quarkus"))
                .body("engine", equalTo("java"))
                .body("contextPath", equalTo(CONTEXT))
                .body("formats", hasItems("docx", "xlsx", "pptx"));
    }

    @Test
    void homePageIsAvailableUnderContextPath() {
        given()
                .when().get(CONTEXT + "/")
                .then()
                .statusCode(200)
                .contentType("text/html")
                .body(containsString("OOXML Compat Normalize"))
                .body(containsString("Normalizza e scarica"));
    }
}
