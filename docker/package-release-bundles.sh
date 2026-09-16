#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/docker-release-bundles}"

JAVA_NAME="OOXML-Compat-Normalize-java-docker-compose"
PYTHON_NAME="OOXML-Compat-Normalize-python-docker-compose"
JAVA_DIR="$OUT/$JAVA_NAME"
PYTHON_DIR="$OUT/$PYTHON_NAME"

rm -rf "$OUT"
mkdir -p "$JAVA_DIR" "$PYTHON_DIR"

# Java / Quarkus bundle. The public bundle uses the conventional docker-compose.yml
# filename while retaining the repository Dockerfile unchanged.
cp "$ROOT/Dockerfile" "$JAVA_DIR/Dockerfile"
cp "$ROOT/docker-compose.java.yml" "$JAVA_DIR/docker-compose.yml"
cp "$ROOT/.dockerignore" "$JAVA_DIR/.dockerignore"
cp "$ROOT/LICENSE" "$ROOT/THIRD_PARTY_NOTICES.md" "$ROOT/THIRD_PARTY_LICENSES.md" "$JAVA_DIR/"
cp "$ROOT/README.md" "$JAVA_DIR/PROJECT-README.md"
cp "$ROOT/docker/README.md" "$JAVA_DIR/DOCKER-README.md"
cp -R "$ROOT/java" "$JAVA_DIR/java"
cp -R "$ROOT/quarkus" "$JAVA_DIR/quarkus"
cat > "$JAVA_DIR/QUICKSTART.md" <<'EOF'
# Java / Quarkus Docker Compose quick start

```bash
docker compose up --build -d
```

Open `http://127.0.0.1:8080/`.

REST API:

- `GET /api/info`
- `POST /api/audit`
- `POST /api/normalize?profile=interop-transitional-v1`

Stop while preserving the log volume with `docker compose down`.
Use `docker compose down -v` only when you also want to delete the persistent logs.
EOF

# Python bundle. Rename Dockerfile.python to the conventional Dockerfile and rewrite
# the copied Compose file to point at it. The self-contained Open XML SDK validator
# source is included because the image builds that helper as part of its multi-stage build.
cp "$ROOT/Dockerfile.python" "$PYTHON_DIR/Dockerfile"
sed 's/dockerfile: Dockerfile\.python/dockerfile: Dockerfile/' \
  "$ROOT/docker-compose.python.yml" > "$PYTHON_DIR/docker-compose.yml"
cp "$ROOT/.dockerignore" "$PYTHON_DIR/.dockerignore"
cp "$ROOT/LICENSE" "$ROOT/THIRD_PARTY_NOTICES.md" "$ROOT/THIRD_PARTY_LICENSES.md" "$PYTHON_DIR/"
cp "$ROOT/README.md" "$PYTHON_DIR/README.md"
cp "$ROOT/docker/README.md" "$PYTHON_DIR/DOCKER-README.md"
cp "$ROOT/pyproject.toml" "$PYTHON_DIR/pyproject.toml"
cp -R "$ROOT/src" "$PYTHON_DIR/src"
mkdir -p "$PYTHON_DIR/dotnet"
cp -R "$ROOT/dotnet/OpenXmlSdkValidator" "$PYTHON_DIR/dotnet/OpenXmlSdkValidator"
cat > "$PYTHON_DIR/QUICKSTART.md" <<'EOF'
# Python Docker Compose quick start

```bash
docker compose up --build -d
```

Open `http://127.0.0.1:8080/`.

REST API:

- `GET /api/info`
- `POST /api/audit`
- `POST /api/normalize?profile=interop-transitional-v1`

The image contains the Python normalization engine and builds a self-contained
Microsoft Open XML SDK validator during the Docker build.

Stop while preserving the log volume with `docker compose down`.
Use `docker compose down -v` only when you also want to delete the persistent logs.
EOF

# Remove build output defensively if this script is run from a non-clean working tree.
find "$JAVA_DIR" "$PYTHON_DIR" -type d \( -name target -o -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} + || true

(
  cd "$OUT"
  zip -q -9 -r "$JAVA_NAME.zip" "$JAVA_NAME"
  zip -q -9 -r "$PYTHON_NAME.zip" "$PYTHON_NAME"
)

python - "$OUT" <<'PY'
from pathlib import Path
import sys
import zipfile

out = Path(sys.argv[1])
for archive in sorted(out.glob("OOXML-Compat-Normalize-*-docker-compose.zip")):
    expected = archive.stem
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    roots = {
        raw.replace("\\", "/").lstrip("./").split("/", 1)[0]
        for raw in names
        if raw.replace("\\", "/").lstrip("./")
    }
    if roots != {expected}:
        raise SystemExit(
            f"{archive.name}: expected exactly one top-level folder {expected!r}, found {sorted(roots)!r}"
        )
    print(f"{archive.name}: top-level folder OK -> {expected}/")
PY

printf '%s\n' "$OUT/$JAVA_NAME.zip" "$OUT/$PYTHON_NAME.zip"
