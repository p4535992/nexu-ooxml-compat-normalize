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
OOXML-Compat-Normalize-java-quarkus.jar
```

Run it with Java 17+:

```bash
java -jar OOXML-Compat-Normalize-java-quarkus.jar
```

Then open:

```text
http://127.0.0.1:8080/
```

## Windows EXE

The Windows release also contains a jpackage-based Java portable and a per-user installer:

```text
OOXML-Compat-Normalize-java-portable-win-x64.zip
OOXML-Compat-Normalize-java-quarkus-installer-win-x64.exe
```

Inside the portable package the primary application launcher is:

```text
OOXML-Compat-Normalize-Quarkus.exe
```

The package includes its Java runtime, so Java does not need to be installed globally. It also contains `ooxml-normalize.cmd` to run the Java core CLI using the same bundled runtime.

The packaging approach follows the same `jpackage` app-image + Windows EXE pattern used by the NexU project.

## Diagnostic logs

File logging is enabled by default. The default path is:

```text
${user.home}/ooxml-compat-normalize-quarkus.log
```

The log rotates at 10 MB, keeps up to 5 backups, and rotates on startup. Override the file location with the `OOXML_LOG_FILE` environment variable.

The release CI does not merely check that the `.exe` exists: it launches the packaged Windows EXE, calls `/api/info`, and verifies that the diagnostic log contains the Quarkus startup marker.

See [`jpackage/LOGS.txt`](jpackage/LOGS.txt).

## Endpoints

- `GET /api/info` — service/version/formats.
- `POST /api/audit` — raw OOXML bytes; requires `X-Filename` header.
- `POST /api/normalize?profile=interop-transitional-v1` — raw OOXML bytes; returns normalized OOXML.

Supported input/output families remain the same: DOCX→DOCX, XLSX→XLSX, PPTX→PPTX.

The Quarkus service delegates normalization to the `ooxml-compat-normalize-java` core library, so there is no duplicate normalization engine.

## License

Project code is MIT. Quarkus and the Quarkus REST extensions are Apache License 2.0. The Java core uses Apache POI and docx4j, also Apache License 2.0. The runtime bundled in portable distributions comes from Eclipse Temurin/OpenJDK 17 under the upstream OpenJDK licensing terms and notices.
