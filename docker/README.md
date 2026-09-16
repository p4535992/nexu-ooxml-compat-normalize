# Docker / Docker Compose

The Docker deployment runs the **Java core through the Quarkus local service**. It is intended for a local Docker environment and does not require Java, Maven, Python or .NET on the host beyond Docker itself.

## Start

From the repository root:

```bash
docker compose up --build -d
```

Then open:

```text
http://127.0.0.1:8080/
```

The REST endpoints remain:

```text
GET  /api/info
POST /api/audit
POST /api/normalize?profile=interop-transitional-v1
```

## Logs

Quarkus writes its rotating file log to:

```text
/data/logs/ooxml-compat-normalize-quarkus.log
```

The `/data/logs` directory is backed by the Docker named volume `ooxml-logs`, so logs survive normal container recreation and `docker compose down`.

Follow stdout/stderr with:

```bash
docker compose logs -f normalizer
```

Inspect the persistent file inside the running container with:

```bash
docker compose exec normalizer cat /data/logs/ooxml-compat-normalize-quarkus.log
```

Copy it to the current host directory when needed:

```bash
docker compose cp normalizer:/data/logs/ooxml-compat-normalize-quarkus.log ./
```

## Stop

Stop/remove containers and the Compose network while preserving the named log volume:

```bash
docker compose down
```

To deliberately delete the persistent log volume too:

```bash
docker compose down -v
```

## Change host port

The default host binding is deliberately loopback-only. To use another port while keeping the service local:

```bash
OOXML_PORT=18080 docker compose up --build -d
```

Then open `http://127.0.0.1:18080/`.

To intentionally bind to another host interface, set `OOXML_BIND_ADDRESS` explicitly. For example, `OOXML_BIND_ADDRESS=0.0.0.0` exposes the mapped port on all host interfaces and should only be used when that network exposure is intended and protected appropriately.

## Container security model

- the application process runs as numeric user `10001`, not root;
- `no-new-privileges` is enabled by Compose;
- browser auto-open is disabled in the container;
- the host HTTP port is bound to `127.0.0.1` by default;
- the persistent log directory uses a Docker named volume rather than a host bind mount, avoiding host ownership mismatches while keeping the process non-root;
- uploaded OOXML files are processed through the existing Quarkus temporary-file flow and are not intentionally persisted in the log volume.

## Build/runtime images and licensing

The image is built locally with the Docker Official `maven` image using Eclipse Temurin 17 and runs on the Docker Official `eclipse-temurin:17-jre` image.

The project does not currently publish a prebuilt Docker image. `docker compose up --build` therefore pulls the upstream build/runtime images and builds this project's image locally.

The final image includes this project's `LICENSE`, `THIRD_PARTY_NOTICES.md` and `THIRD_PARTY_LICENSES.md` under `/app/licenses`. The Eclipse Temurin/OpenJDK base image retains its own upstream runtime legal material under the JRE's `legal/` directory. See `docs/licensing.md` and `docs/licensing-audit.md` for the project-level licensing summary/checklist.
