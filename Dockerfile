# syntax=docker/dockerfile:1.7

FROM maven:3.9.16-eclipse-temurin-17 AS build
WORKDIR /workspace

COPY java/ java/
COPY quarkus/ quarkus/

RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -ntp -f java/pom.xml clean install -DskipTests \
    && mvn -B -ntp -f quarkus/pom.xml clean package -DskipTests \
    && runner="$(find quarkus/target -maxdepth 1 -type f -name '*-runner.jar' -print -quit)" \
    && test -n "$runner" \
    && cp "$runner" /tmp/ooxml-compat-normalize-quarkus.jar

FROM eclipse-temurin:17-jre

LABEL org.opencontainers.image.title="OOXML Compat Normalize - Quarkus" \
      org.opencontainers.image.description="Local OOXML normalization web/API service" \
      org.opencontainers.image.source="https://github.com/p4535992/ooxml-compat-normalize"

WORKDIR /app

COPY --from=build /tmp/ooxml-compat-normalize-quarkus.jar /app/ooxml-compat-normalize-quarkus.jar
COPY LICENSE THIRD_PARTY_NOTICES.md THIRD_PARTY_LICENSES.md /app/licenses/

RUN mkdir -p /data/logs \
    && chown -R 10001:0 /app /data \
    && chmod -R g=u /app /data

# Quarkus must listen on the container interface; docker-compose publishes it
# on host loopback only by default.
ENV QUARKUS_HTTP_HOST=0.0.0.0 \
    QUARKUS_HTTP_PORT=8080 \
    OOXML_CONTEXT_PATH=/ooxml-compat-normalize \
    OOXML_LOG_FILE=/data/logs/ooxml-compat-normalize-quarkus.log \
    OOXML_OPEN_BROWSER=false

USER 10001
EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/ooxml-compat-normalize-quarkus.jar"]
