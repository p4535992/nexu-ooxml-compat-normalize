# Docker / Docker Compose

The repository exposes **three Docker stacks** with the same context-prefixed web/REST model:

- `docker-compose.java.yml` — Java core through Quarkus only;
- `docker-compose.python.yml` — Python normalization engine only, with the self-contained Microsoft Open XML SDK validator bundled in the image;
- `docker-compose.combined.yml` — one container that contains **both Java/Quarkus and Python**, with a small gateway/UI that lets the user select the engine per operation.

All listen on host loopback port **8080 by default** and expose the UI under the shared context path:

```text
http://127.0.0.1:8080/ooxml-compat-normalize/
```

The default context path is:

```text
/ooxml-compat-normalize
```

Override it for any stack with `OOXML_CONTEXT_PATH`, for example `OOXML_CONTEXT_PATH=/office-normalizer`.

Only one stack can own `127.0.0.1:8080` at a time. To run multiple stacks simultaneously, assign a different `OOXML_PORT` to each additional stack.

## Combined Java + Python stack

Start the single container containing both engines:

```bash
docker compose -f docker-compose.combined.yml up --build -d
```

Open:

```text
http://127.0.0.1:8080/ooxml-compat-normalize/
```

The page exposes an **Engine** selector with:

```text
Python
Java / Quarkus
```

The selected engine is used for both **Analizza** and **Normalizza e scarica**. No extra host ports are exposed: the gateway is the only process listening on the published container port, while Java and Python listen on separate loopback-only ports inside the same container.

The default engine is Python and can be changed at startup:

```bash
OOXML_DEFAULT_ENGINE=java docker compose -f docker-compose.combined.yml up --build -d
```

Stop while preserving logs:

```bash
docker compose -f docker-compose.combined.yml down
```

Delete the persistent log volume as well:

```bash
docker compose -f docker-compose.combined.yml down -v
```

### Selecting the engine through REST

For the combined stack, pass the engine as a query parameter:

```text
GET  /ooxml-compat-normalize/api/info?engine=java
GET  /ooxml-compat-normalize/api/info?engine=python
POST /ooxml-compat-normalize/api/audit?engine=java
POST /ooxml-compat-normalize/api/audit?engine=python
POST /ooxml-compat-normalize/api/normalize?engine=java&profile=interop-transitional-v1
POST /ooxml-compat-normalize/api/normalize?engine=python&profile=interop-transitional-v1
```

`X-OOXML-Engine: java` or `X-OOXML-Engine: python` is also accepted for POST requests. The query parameter takes precedence when both are present. If neither is supplied, `OOXML_DEFAULT_ENGINE` is used.

`GET /ooxml-compat-normalize/api/info` without an engine returns combined metadata plus information reported by both embedded engines.

Normalization responses expose:

```text
X-OOXML-Selected-Engine: java|python
X-OOXML-Engine: java|python
```

so a client can verify which normalizer produced the file.

## Java / Quarkus stack

Start:

```bash
docker compose -f docker-compose.java.yml up --build -d
```

Open:

```text
http://127.0.0.1:8080/ooxml-compat-normalize/
```

Stop while preserving logs:

```bash
docker compose -f docker-compose.java.yml down
```

Delete the persistent log volume as well:

```bash
docker compose -f docker-compose.java.yml down -v
```

The Java container runs the Quarkus service and reuses the Java normalizer core; it does not invoke Python.

## Python stack

Start:

```bash
docker compose -f docker-compose.python.yml up --build -d
```

Open:

```text
http://127.0.0.1:8080/ooxml-compat-normalize/
```

Stop while preserving logs:

```bash
docker compose -f docker-compose.python.yml down
```

Delete the persistent log volume as well:

```bash
docker compose -f docker-compose.python.yml down -v
```

The Python image runs the same Python normalization engine used by the CLI/desktop application. The image also builds and bundles the self-contained Open XML SDK validator, and Docker configures SDK validation as `required`.

## Run separate Java and Python stacks at the same time

For example, keep Java on port 8080 and run Python on port 8081:

```bash
docker compose -f docker-compose.java.yml up --build -d
OOXML_PORT=8081 docker compose -f docker-compose.python.yml up --build -d
```

Then:

```text
Java:   http://127.0.0.1:8080/ooxml-compat-normalize/
Python: http://127.0.0.1:8081/ooxml-compat-normalize/
```

Use the combined stack instead when one exposed service with a per-operation engine selector is more convenient.

## Shared REST API

The Java-only and Python-only implementations expose the same paths under the context prefix:

```text
GET  /ooxml-compat-normalize/api/info
POST /ooxml-compat-normalize/api/audit
POST /ooxml-compat-normalize/api/normalize?profile=interop-transitional-v1
```

The combined stack exposes those same routes and adds the optional `engine=java|python` selector described above.

`GET /ooxml-compat-normalize/api/info` also reports the active `contextPath`, so clients do not need to infer it.

Supported profiles:

```text
preserve-v1
interop-transitional-v1
portable-explicit-v1
```

For the audit and normalize endpoints:

- request body: raw DOCX/XLSX/PPTX bytes (`application/octet-stream`);
- required header: `X-Filename` containing the original filename including extension;
- `.../api/audit` returns JSON;
- `.../api/normalize` returns the normalized OOXML file as `application/octet-stream` with `Content-Disposition`.

### curl

Audit with a dedicated Java/Python stack:

```bash
curl -f \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  -H "X-Filename: document.docx" \
  --data-binary @document.docx \
  http://127.0.0.1:8080/ooxml-compat-normalize/api/audit
```

Audit with the combined stack and Java selected:

```bash
curl -f \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  -H "X-Filename: document.docx" \
  --data-binary @document.docx \
  "http://127.0.0.1:8080/ooxml-compat-normalize/api/audit?engine=java"
```

Normalize with the combined stack and Python selected:

```bash
curl -f \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  -H "X-Filename: document.docx" \
  --data-binary @document.docx \
  "http://127.0.0.1:8080/ooxml-compat-normalize/api/normalize?engine=python&profile=interop-transitional-v1" \
  -o document-normalized.docx
```

### Python client code

No third-party client library is required:

```python
from pathlib import Path
from urllib.request import Request, urlopen

src = Path("document.docx")
request = Request(
    "http://127.0.0.1:8080/ooxml-compat-normalize/api/normalize?profile=interop-transitional-v1",
    data=src.read_bytes(),
    method="POST",
    headers={
        "Content-Type": "application/octet-stream",
        "X-Filename": src.name,
    },
)
with urlopen(request) as response:
    Path("document-normalized.docx").write_bytes(response.read())
```

The same client code can call either dedicated engine. For the combined stack, add `engine=java` or `engine=python` to the query string.

### Java client code

Java 11+ can use `java.net.http.HttpClient`:

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;

Path input = Path.of("document.docx");
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("http://127.0.0.1:8080/ooxml-compat-normalize/api/normalize?profile=interop-transitional-v1"))
    .header("Content-Type", "application/octet-stream")
    .header("X-Filename", input.getFileName().toString())
    .POST(HttpRequest.BodyPublishers.ofByteArray(Files.readAllBytes(input)))
    .build();

HttpResponse<byte[]> response = HttpClient.newHttpClient().send(
    request,
    HttpResponse.BodyHandlers.ofByteArray()
);
if (response.statusCode() != 200) {
    throw new IllegalStateException("HTTP " + response.statusCode());
}
Files.write(Path.of("document-normalized.docx"), response.body());
```

## Logs

The Java stack uses the named volume `ooxml-java-logs` and writes:

```text
/data/logs/ooxml-compat-normalize-quarkus.log
```

The Python stack uses the named volume `ooxml-python-logs` and writes:

```text
/data/logs/ooxml-compat-normalize-python.log
```

The combined stack uses `ooxml-combined-logs` and writes all three diagnostic logs:

```text
/data/logs/ooxml-compat-normalize-gateway.log
/data/logs/ooxml-compat-normalize-quarkus.log
/data/logs/ooxml-compat-normalize-python.log
```

Normal `docker compose down` preserves each named volume. `down -v` deliberately deletes it.

## Change host port, context path or bind address

All compose files accept the same base variables. To use another local port:

```bash
OOXML_PORT=18080 docker compose -f docker-compose.combined.yml up --build -d
```

To use a different application context path:

```bash
OOXML_CONTEXT_PATH=/office-normalizer docker compose -f docker-compose.combined.yml up --build -d
```

The corresponding UI becomes `http://127.0.0.1:8080/office-normalizer/` and the API begins at `/office-normalizer/api/`.

The default host binding is deliberately loopback-only. Set `OOXML_BIND_ADDRESS=0.0.0.0` only when intentional network exposure is required and properly protected.

## Downloadable Docker bundles

The project keeps the established Java and Python Docker Compose ZIP names available after adding the combined container, and adds **TAR.GZ alternatives** for all three variants:

```text
OOXML-Compat-Normalize-java-docker-compose.zip
OOXML-Compat-Normalize-java-docker-compose.tar.gz

OOXML-Compat-Normalize-python-docker-compose.zip
OOXML-Compat-Normalize-python-docker-compose.tar.gz

OOXML-Compat-Normalize-combined-docker-compose.zip
OOXML-Compat-Normalize-combined-docker-compose.tar.gz

SHA256SUMS-docker.txt
```

Each archive has exactly one top-level directory matching the archive name without `.zip` or `.tar.gz`. Inside that directory the selected compose file is named simply:

```text
docker-compose.yml
```

so after extraction the usual command is enough:

```bash
docker compose up --build -d
```

The bundles include the source files needed by their corresponding Docker build; they do not require cloning the repository separately.

`.github/workflows/docker-bundles.yml` creates and verifies these archives on relevant `main` changes. Permanent downloads are attached directly to each GitHub Release, avoiding dependency on the GitHub Actions temporary-artifact quota. A manual workflow run can also attach them to a specific existing release tag.

## Container security model

All three stacks:

- run the exposed application/gateway process as numeric user `10001`, not root;
- enable `no-new-privileges`;
- bind the published host port to `127.0.0.1` by default;
- persist only diagnostic logs in a named Docker volume;
- process uploaded OOXML through temporary files and do not intentionally persist document contents in the log volume.

The dedicated Java image preserves the Temurin/OpenJDK `legal/` material supplied by its base image. The Python image retains the project notices and copies the .NET SDK/runtime license and third-party notice used to build its self-contained Open XML SDK validator under `/app/licenses/dotnet/`.

The combined image includes Debian OpenJDK 17 plus its package copyright notice, and the same self-contained Open XML SDK validator/license material used by the Python image.

## CI coverage

`.github/workflows/docker-smoke.yml` exercises all three deployment modes. The dedicated Java/Python matrix verifies the shared API contract independently. The combined job additionally verifies that **the same running container** can:

- expose the engine selector in the HTML page;
- report both embedded engines;
- audit and normalize a DOCX with `engine=python`;
- audit and normalize the same DOCX with `engine=java`;
- return the selected engine in response headers;
- keep REST routes under the configured context path;
- preserve separate gateway, Java and Python diagnostic logs;
- run as a non-root user and restart with both engines available.
