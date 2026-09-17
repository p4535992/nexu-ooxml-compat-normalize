# Docker / Docker Compose

The repository exposes **three Docker stacks** with the same context-prefixed web/REST model:

- `docker-compose.java.yml` — Java core through Quarkus only;
- `docker-compose.python.yml` — Python normalization engine only, with the self-contained Microsoft Open XML SDK validator bundled in the image;
- `docker-compose.combined.yml` — one container containing **both Java/Quarkus and Python**, fronted by a small gateway/UI.

All stacks publish host loopback port **8080 by default** and expose the UI at:

```text
http://127.0.0.1:8080/ooxml-compat-normalize/
```

The default context path is `/ooxml-compat-normalize` and can be overridden with `OOXML_CONTEXT_PATH`.

## Combined Java + Python stack

Start:

```bash
docker compose -f docker-compose.combined.yml up --build -d
```

The combined container supports three runtime modes:

```text
both    Python + Java enabled (default)
python  only Python enabled
java    only Java / Quarkus enabled
```

The startup mode can be selected with:

```bash
OOXML_ENGINE_MODE=python docker compose -f docker-compose.combined.yml up --build -d
OOXML_ENGINE_MODE=java docker compose -f docker-compose.combined.yml up --build -d
```

`OOXML_ENGINE_MODE=both` is the default. `OOXML_DEFAULT_ENGINE=python|java` controls which engine is selected by default when both engines are enabled.

### Change mode from the HTML page

The combined web page contains:

- a **Modalità** selector: `Python + Java`, `Solo Python`, `Solo Java / Quarkus`;
- an **Engine** selector used for the individual audit/normalization operation.

Changing the mode is a real runtime operation. For example, switching from `both` to `python` stops the Java backend process; switching to `java` stops the Python backend. Returning to `both` starts the missing backend again.

No additional host ports are exposed. The gateway alone listens on the published port `8080`; Java and Python use separate loopback-only ports inside the same container.

### Change mode through REST

Current mode:

```text
GET /ooxml-compat-normalize/api/mode
```

Set a mode:

```text
POST /ooxml-compat-normalize/api/mode?mode=both
POST /ooxml-compat-normalize/api/mode?mode=python
POST /ooxml-compat-normalize/api/mode?mode=java
```

Example:

```bash
curl -f -X POST \
  'http://127.0.0.1:8080/ooxml-compat-normalize/api/mode?mode=python'
```

The response reports:

```json
{
  "mode": "python",
  "enabledEngines": ["python"],
  "defaultEngine": "python"
}
```

Requests for a disabled engine return HTTP `409 Conflict`.

### Select an engine for an operation

When the mode is `both`, select the engine with the query parameter:

```text
GET  /ooxml-compat-normalize/api/info?engine=java
GET  /ooxml-compat-normalize/api/info?engine=python
POST /ooxml-compat-normalize/api/audit?engine=java
POST /ooxml-compat-normalize/api/audit?engine=python
POST /ooxml-compat-normalize/api/normalize?engine=java&profile=interop-transitional-v1
POST /ooxml-compat-normalize/api/normalize?engine=python&profile=interop-transitional-v1
```

For POST requests, `X-OOXML-Engine: java|python` is also accepted. The query parameter takes precedence. If no engine is supplied, the current effective default engine is used.

Normalization responses include:

```text
X-OOXML-Selected-Engine: java|python
X-OOXML-Engine-Mode: both|python|java
X-OOXML-Engine: java|python
```

## Java-only stack

```bash
docker compose -f docker-compose.java.yml up --build -d
```

This container runs Quarkus and the Java normalizer only; it does not invoke Python.

## Python-only stack

```bash
docker compose -f docker-compose.python.yml up --build -d
```

This container runs the Python engine plus the self-contained Microsoft Open XML SDK validator; it does not invoke Java normalizer code.

## Shared REST API

The Java-only and Python-only stacks expose:

```text
GET  /ooxml-compat-normalize/api/info
POST /ooxml-compat-normalize/api/audit
POST /ooxml-compat-normalize/api/normalize?profile=interop-transitional-v1
```

The combined stack exposes the same operations plus `/api/mode` and optional `engine=java|python` routing.

For audit/normalization:

- body: raw DOCX/XLSX/PPTX bytes (`application/octet-stream`);
- required header: `X-Filename` with the original filename and extension;
- audit returns JSON;
- normalize returns the normalized OOXML file.

Example:

```bash
curl -f \
  -X POST \
  -H 'Content-Type: application/octet-stream' \
  -H 'X-Filename: document.docx' \
  --data-binary @document.docx \
  'http://127.0.0.1:8080/ooxml-compat-normalize/api/normalize?engine=python&profile=interop-transitional-v1' \
  -o document-normalized.docx
```

Supported profiles:

```text
preserve-v1
interop-transitional-v1
portable-explicit-v1
```

## Operator-friendly bundle scripts

Every downloadable Docker Compose ZIP/TAR.GZ contains these executable helper scripts at the top level of its single root directory:

```text
start_all.sh
down_all.sh
```

They deliberately work relative to their own directory, so an operator does not need to remember the Compose command or change directory manually.

Start/build in detached mode:

```bash
./start_all.sh
```

This executes the equivalent of:

```bash
docker compose up --build -d
```

and prints the expected web URL plus `docker compose ps`.

Stop the stack:

```bash
./down_all.sh
```

This executes:

```bash
docker compose down
```

It intentionally does **not** use `-v`, so persistent diagnostic log volumes are preserved.

Both scripts check that Docker and the `docker compose` plugin are available and print a clear error otherwise.

## Run separate stacks simultaneously

Only one stack can own `127.0.0.1:8080` at a time. Example:

```bash
docker compose -f docker-compose.java.yml up --build -d
OOXML_PORT=8081 docker compose -f docker-compose.python.yml up --build -d
```

Then:

```text
Java:   http://127.0.0.1:8080/ooxml-compat-normalize/
Python: http://127.0.0.1:8081/ooxml-compat-normalize/
```

## Port, context path and bind address

Alternative port:

```bash
OOXML_PORT=18080 docker compose -f docker-compose.combined.yml up --build -d
```

Alternative context:

```bash
OOXML_CONTEXT_PATH=/office-normalizer docker compose -f docker-compose.combined.yml up --build -d
```

The default host binding is loopback-only. Set `OOXML_BIND_ADDRESS=0.0.0.0` only when intentional network exposure is required and properly protected.

## Logs

Java-only:

```text
/data/logs/ooxml-compat-normalize-quarkus.log
```

Python-only:

```text
/data/logs/ooxml-compat-normalize-python.log
```

Combined:

```text
/data/logs/ooxml-compat-normalize-gateway.log
/data/logs/ooxml-compat-normalize-quarkus.log
/data/logs/ooxml-compat-normalize-python.log
```

A normal `docker compose down` preserves the named log volume. `docker compose down -v` deliberately removes it.

## Downloadable Docker bundles

Release packaging keeps the established Java/Python ZIP names and provides equivalent TAR.GZ files plus the combined variant:

```text
OOXML-Compat-Normalize-java-docker-compose.zip
OOXML-Compat-Normalize-java-docker-compose.tar.gz

OOXML-Compat-Normalize-python-docker-compose.zip
OOXML-Compat-Normalize-python-docker-compose.tar.gz

OOXML-Compat-Normalize-combined-docker-compose.zip
OOXML-Compat-Normalize-combined-docker-compose.tar.gz

SHA256SUMS-docker.txt
```

Every archive has exactly one first-level directory matching its filename without `.zip` or `.tar.gz`. That directory contains:

```text
docker-compose.yml
start_all.sh
down_all.sh
...
```

plus all source files required to build that variant without cloning the repository separately.

`.github/workflows/docker-bundles.yml` validates all six archives, the root directory name, `docker-compose.yml`, shell syntax and executable mode of both helper scripts. Permanent downloads are attached directly to GitHub Releases rather than relying on temporary Actions artifact storage.

## Container security model

All stacks:

- run the exposed application/gateway as numeric user `10001`, not root;
- enable `no-new-privileges`;
- bind the published host port to `127.0.0.1` by default;
- persist only diagnostic logs in a named Docker volume;
- process uploaded OOXML with temporary files and do not intentionally persist document contents in the log volume.

The Java image preserves the runtime legal material supplied by its OpenJDK base. The Python image retains the project notices plus the .NET/Open XML SDK validator license material. The combined image includes both Java runtime legal material and the .NET validator license/third-party notices.

## CI coverage

`.github/workflows/docker-smoke.yml` tests Java-only, Python-only and combined normalization. The combined test audits and normalizes a DOCX with both engines.

`.github/workflows/docker-combined-mode-smoke.yml` additionally verifies the runtime mode controller:

```text
both -> python -> java -> both
```

and checks that the disabled backend process is actually stopped, disabled-engine REST calls return `409`, and both engines are restored after returning to `both`.
