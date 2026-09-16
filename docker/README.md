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

Container logs produced by Quarkus are persisted on the host under:

```text
./docker-data/logs/ooxml-compat-normalize-quarkus.log
```

Docker stdout/stderr remains available through:

```bash
docker compose logs -f normalizer
```

## Stop

```bash
docker compose down
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
- only the HTTP port and the persistent log directory are exposed by default;
- uploaded OOXML files are processed through the existing Quarkus temporary-file flow and are not intentionally persisted in the mounted log directory.

## Build/runtime images and licensing

The image is built locally with the Docker Official `maven` image using Eclipse Temurin 17 and runs on the Docker Official `eclipse-temurin:17-jre` image.

The project does not currently publish a prebuilt Docker image. `docker compose up --build` therefore pulls the upstream build/runtime images and builds this project's image locally.

The final image includes this project's `LICENSE`, `THIRD_PARTY_NOTICES.md` and `THIRD_PARTY_LICENSES.md` under `/app/licenses`. The Eclipse Temurin/OpenJDK base image retains its own upstream runtime legal material. See `docs/licensing.md` for the project-level licensing summary.
