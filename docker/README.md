# Docker / Docker Compose

The repository exposes **two independent Docker stacks** with the same web/REST contract:

- `docker-compose.java.yml` — Java core through Quarkus;
- `docker-compose.python.yml` — Python normalization engine through the standard-library HTTP service, with the self-contained Microsoft Open XML SDK validator bundled in the image.

Both listen on host loopback port **8080 by default** and expose the UI under the shared context path:

```text
http://127.0.0.1:8080/ooxml-compat-normalize/
```

The default context path is:

```text
/ooxml-compat-normalize
```

Override it for either stack with `OOXML_CONTEXT_PATH`, for example `OOXML_CONTEXT_PATH=/office-normalizer`.

Only one stack can own `127.0.0.1:8080` at a time. To run both simultaneously, keep one on 8080 and set `OOXML_PORT` for the other.

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

## Run both at the same time

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

## Shared REST API

Both implementations expose the same paths under the context prefix:

```text
GET  /ooxml-compat-normalize/api/info
POST /ooxml-compat-normalize/api/audit
POST /ooxml-compat-normalize/api/normalize?profile=interop-transitional-v1
```

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

Audit:

```bash
curl -f \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  -H "X-Filename: document.docx" \
  --data-binary @document.docx \
  http://127.0.0.1:8080/ooxml-compat-normalize/api/audit
```

Normalize:

```bash
curl -f \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  -H "X-Filename: document.docx" \
  --data-binary @document.docx \
  "http://127.0.0.1:8080/ooxml-compat-normalize/api/normalize?profile=interop-transitional-v1" \
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

The same client code can call either the Java or Python container because the HTTP contract is shared.

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

Inspect it with:

```bash
docker compose -f docker-compose.java.yml exec normalizer-java \
  cat /data/logs/ooxml-compat-normalize-quarkus.log
```

The Python stack uses the named volume `ooxml-python-logs` and writes:

```text
/data/logs/ooxml-compat-normalize-python.log
```

Inspect it with:

```bash
docker compose -f docker-compose.python.yml exec normalizer-python \
  cat /data/logs/ooxml-compat-normalize-python.log
```

Normal `docker compose down` preserves each named volume. `down -v` deliberately deletes it.

## Change host port, context path or bind address

Both compose files accept the same variables. To use another local port:

```bash
OOXML_PORT=18080 docker compose -f docker-compose.java.yml up --build -d
```

To use a different application context path:

```bash
OOXML_CONTEXT_PATH=/office-normalizer docker compose -f docker-compose.java.yml up --build -d
```

The corresponding UI becomes `http://127.0.0.1:8080/office-normalizer/` and the API begins at `/office-normalizer/api/`.

The default host binding is deliberately loopback-only. Set `OOXML_BIND_ADDRESS=0.0.0.0` only when intentional network exposure is required and properly protected.

## Container security model

Both stacks:

- run the application process as numeric user `10001`, not root;
- enable `no-new-privileges`;
- bind the published host port to `127.0.0.1` by default;
- persist only diagnostic logs in a named Docker volume;
- process uploaded OOXML through temporary files and do not intentionally persist document contents in the log volume.

The Java image preserves the Temurin/OpenJDK `legal/` material supplied by its base image. The Python image retains the project notices and copies the .NET SDK/runtime license and third-party notice used to build its self-contained Open XML SDK validator under `/app/licenses/dotnet/`.

## CI coverage

`.github/workflows/docker-smoke.yml` builds and exercises **both** stacks. For each engine it verifies:

- the context-prefixed `.../api/info` route and reported `contextPath`;
- the context-prefixed web page;
- that root-level `/api/info` is not exposed;
- a real `POST .../api/audit` using a generated DOCX fixture;
- a real `POST .../api/normalize` and ZIP integrity of the returned DOCX;
- persistent file logging;
- non-root execution;
- license/legal material;
- successful service restart while keeping the log volume.
