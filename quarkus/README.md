# Quarkus local service

Small local web/API wrapper around the Java core normalizer.

It is intentionally local-first: by default it listens only on `127.0.0.1:8080` and does not send documents to external services.

## Build

First install the Java core into the local Maven repository, then build Quarkus:

```bash
mvn -B -f java/pom.xml clean install
mvn -B -f quarkus/pom.xml clean verify package
```

The release workflow builds an executable Quarkus uber-JAR named:

```text
ooxml-compat-normalize-quarkus.jar
```

Run it with Java 17+:

```bash
java -jar ooxml-compat-normalize-quarkus.jar
```

Then open:

```text
http://127.0.0.1:8080/
```

## Endpoints

- `GET /api/info` — service/version/formats.
- `POST /api/audit` — raw OOXML bytes; requires `X-Filename` header.
- `POST /api/normalize?profile=interop-transitional-v1` — raw OOXML bytes; returns normalized OOXML.

Supported input/output families remain the same: DOCX→DOCX, XLSX→XLSX, PPTX→PPTX.

The Quarkus service delegates normalization to the `ooxml-compat-normalize-java` core library, so there is no duplicate normalization engine.

## License

Project code is MIT. Quarkus and the Quarkus REST extensions are Apache License 2.0. The Java core uses Apache POI and docx4j, also Apache License 2.0.
