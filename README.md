# ooxml-compat-normalize

Loss-averse OOXML interoperability normalizer for **DOCX, XLSX and PPTX**.

The project is intentionally **not** a LibreOffice → ONLYOFFICE converter, nor an ONLYOFFICE → LibreOffice converter. Its goal is to normalize documents produced by LibreOffice, ONLYOFFICE, Microsoft Office and other OOXML consumers toward a **common, explicit and cross-suite OOXML representation** that can then be consumed again by any of those applications.

Conceptually, the project is **N → 1 → N**:

```text
LibreOffice ----┐                         ┌---- LibreOffice
ONLYOFFICE -----┤                         ├---- ONLYOFFICE
Microsoft Office├--> normalized OOXML --->├---- Microsoft Office
other OOXML ----┘                         └---- other OOXML
```

There is no preferred source suite and no preferred target suite. The same normalized DOCX/XLSX/PPTX should remain useful when moving in either direction between applications.

## Goal

Create a practical common OOXML representation that minimizes cross-suite interpretation differences while preserving as much author intent as possible:

- font identity and font intent;
- direct and theme colors;
- Word/Excel/PowerPoint styles;
- tables, cells, shapes and drawing anchors;
- themes and inheritance;
- images/media;
- relationships and content types;
- headers, footers, notes and auxiliary parts;
- unknown/vendor parts unless a rule explicitly owns them.

The preferred transformation is:

```text
source semantics
      ↓
resolve only safe/known OOXML ambiguity
      ↓
explicit, standard OOXML semantics
      ↓
LibreOffice / ONLYOFFICE / Microsoft Office / other consumers
```

No tool can promise pixel-identical rendering across every office suite because installed font files, shaping engines, layout engines and vendor-specific features remain environment-dependent. The project therefore prefers **preserve + report** over silent destructive rewriting.

## Pipeline

```text
LibreOffice / ONLYOFFICE / Microsoft Office / altro
                         ↓
                  PRE-FLIGHT AUDIT
                         ↓
          font / temi / stili / colori
          feature complesse / relazioni
          tipo OOXML / produttore
                         ↓
               NORMALIZZAZIONE OOXML
                ↙         ↓         ↘
             DOCX        XLSX       PPTX
                         ↓
                POST-FLIGHT AUDIT
                         ↓
           verifica che nulla sia sparito
                         ↓
                 OOXML normalizzato
                ↙         ↓         ↘
        LibreOffice   ONLYOFFICE   Microsoft Office
                         +
                  altri consumer OOXML
```

The normalized file has **no target-application flag**. LibreOffice, ONLYOFFICE and Microsoft Office are peers in the interoperability model.

## Profiles

The output always remains in the **same OOXML family**: DOCX → DOCX, XLSX → XLSX, PPTX → PPTX.

| Profile | Purpose |
| --- | --- |
| `preserve-v1` | Preserve package semantics; useful for audit/copy workflows and explicit user mappings. |
| `interop-transitional-v1` | Recommended conservative cross-suite profile; normalizes proven renderer-dependent constructs while preserving safe semantics. |
| `portable-explicit-v1` | Additionally materializes theme fonts/colors and safe implicit defaults where the result is unambiguous. |

`portable-explicit-v1` never means “optimize for one office suite”. It means “make the same OOXML meaning more explicit when it can be resolved safely”.

## Current implementation

| Area | DOCX | XLSX | PPTX |
| --- | --- | --- | --- |
| Package-preserving copy + ZIP verification | ✅ | ✅ | ✅ |
| Producer/conformance/font/risk preflight | ✅ | ✅ | ✅ |
| Exact font mapping in real font declarations | ✅ | ✅ | ✅ |
| Font inventory validation | ✅ | ✅ | ✅ |
| Renderer-dependent color symbols → explicit OOXML color | ✅ simple runs | ✅ rich-text runs | ✅ simple DrawingML runs |
| Theme-font materialization (`portable-explicit-v1`) | ✅ `w:rFonts` | ✅ styles + DrawingML | ✅ DrawingML placeholders |
| Theme-color materialization without unsupported transforms | ✅ | ✅ | ✅ |
| Word implicit table layout → explicit `autofit` | ✅ | — | — |
| Word style inheritance diagnostics | ✅ | — | — |
| Excel custom number-format diagnostics | — | ✅ | — |
| Excel conditional-format priority diagnostics | — | ✅ | — |
| Excel `twoCellAnchor` default → explicit `editAs="twoCell"` | — | ✅ | — |
| PowerPoint slide/layout/master/theme inheritance | — | — | ✅ |
| PowerPoint implicit text-autofit diagnostics | — | — | ✅ |
| Unknown/vendor parts preserved | ✅ | ✅ | ✅ |
| Strict OOXML → Transitional conversion | planned | planned | planned |

Risky transformations remain diagnostics until semantic equivalence is demonstrated with regression fixtures.

## Font strategy

Font handling follows the same N → 1 → N principle. There is **no default target suite**.

The default behavior is **preserve font identity and semantics**:

- keep explicitly declared font family names unchanged;
- resolve theme/font inheritance only when the result is unambiguous and the selected profile calls for it;
- never substitute a family merely because another suite might prefer a different one;
- inventory required fonts and report environment dependencies separately from document normalization.

### GUI font modes

| Mode | Behavior |
| --- | --- |
| **Preserva esattamente i font originali** | **Default.** No automatic family substitution. |
| **Sostituisci solo i font mancanti** | Keeps every available source font; uses a known metric-compatible fallback only when the source is missing and the fallback exists locally. |
| **Forza profilo compatibile** | Explicit opt-in mapping such as Arial → Liberation Sans and Calibri → Carlito. |
| **Mapping personalizzato** | User-defined `OLD=NEW` mappings, optionally restricted to missing source fonts. |

The non-default modes are **environment/user policy**, not part of the canonical representation.

## Python CLI and web service

CLI:

```bash
ooxml-compat-normalize input.docx --audit-only --report preflight.json

ooxml-compat-normalize input.docx output.docx \
  --profile interop-transitional-v1 \
  --report output.report.json
```

The Python package also exposes a lightweight standard-library HTTP service:

```bash
ooxml-compat-normalize-web
```

By default it listens on:

```text
http://127.0.0.1:8080/
```

It uses the same Python normalization engine as the CLI; it is not a separate implementation.

## Python desktop portable

The Tkinter GUI supports selecting one or more `.docx`, `.xlsx` or `.pptx` files, choosing the normalization profile and font policy, and writing JSON reports.

Windows/Linux Python portable builds embed a self-contained **.NET / Microsoft Open XML SDK** validator. End users do not need Python or .NET installed.

The release names always include `python` explicitly:

```text
OOXML-Compat-Normalize-python-portable-win-x64.zip
OOXML-Compat-Normalize-python-portable-linux-x64.tar.gz
```

See [`portable/README.md`](portable/README.md).

## Java core

The Java implementation is a real library/CLI, not a wrapper around Python.

It uses:

- **Apache POI 5.5.1** as a cross-format OPC/OOXML parser;
- **docx4j 17.1.0** as a second independent OOXML parser/model;
- JDK ZIP/XML primitives for the actual package-preserving writer.

POI/docx4j are used for **pre-flight and post-flight parsing/validation**, not to re-save the complete document.

Build locally:

```bash
mvn -f java/pom.xml clean install
```

The standalone release artifact is named explicitly:

```text
OOXML-Compat-Normalize-java-core.jar
```

Usage:

```bash
java -jar OOXML-Compat-Normalize-java-core.jar input.docx output.docx
java -jar OOXML-Compat-Normalize-java-core.jar input.xlsx --audit-only
```

See [`java/README.md`](java/README.md).

## Quarkus local service

A small **Quarkus 3.39.3** application exposes the same Java core through a local web UI and REST API. It does not implement a separate normalization engine.

By default it binds only to IPv4 loopback:

```text
127.0.0.1:8080
```

The raw release JAR is:

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

Use the explicit `127.0.0.1` address rather than `localhost`: on systems where `localhost` resolves to IPv6 `::1` first, `http://localhost:8080/` can fail while the IPv4-only local service is healthy.

The packaged Windows `.exe` waits for the local service and automatically opens `http://127.0.0.1:8080/` in the default browser. A manual `open-ui.cmd` is also included.

Available endpoints:

- `GET /api/info`
- `POST /api/audit`
- `POST /api/normalize?profile=interop-transitional-v1`

### Diagnostic logging

Portable Quarkus distributions keep logs **inside the extracted application directory**, following the NexU portable pattern.

Windows portable:

```text
OOXML-Compat-Normalize-java-portable-win-x64/
├─ OOXML-Compat-Normalize-Quarkus.exe
├─ LOGS.txt
└─ logs/
   └─ ooxml-compat-normalize-quarkus.log
```

Linux portable uses the same `logs/` directory beside `ooxml-quarkus`.

For the raw JAR, the default is relative to the directory from which it is launched:

```text
./logs/ooxml-compat-normalize-quarkus.log
```

The rotation policy is 10 MB × 5 backups with rotate-on-start. Raw-JAR launches can override the file with `OOXML_LOG_FILE`. Logs include startup, audit/normalization operations, selected profile, validation status and error information; the application does not intentionally log document contents.

See [`quarkus/README.md`](quarkus/README.md) and [`quarkus/jpackage/LOGS.txt`](quarkus/jpackage/LOGS.txt).

## Java portable distribution and Windows EXE

For machines where Java is not installed, releases contain Java portable packages for Windows and Linux. Both include a Java 17 runtime plus the **core JAR and Quarkus JAR**.

Release names:

```text
OOXML-Compat-Normalize-java-portable-win-x64.zip
OOXML-Compat-Normalize-java-portable-linux-x64.tar.gz
```

On Windows the portable package is built with **jpackage**, following the same delivery pattern used by the NexU project. It contains a real executable launcher:

```text
OOXML-Compat-Normalize-Quarkus.exe
```

and also a core CLI launcher:

```text
ooxml-normalize.cmd
```

The same build also creates a Windows per-user installer:

```text
OOXML-Compat-Normalize-java-quarkus-installer-win-x64.exe
```

On Linux the portable contains the bundled runtime, both Java JARs, launchers, notices and `logs/` directory. No global Java installation is required.

## Java o Python: quale normalizzatore è migliore?

The project intentionally keeps **two independent normalization runtimes**. The goal is not to make one language win, but to converge both implementations toward the same OOXML semantics and use the differences as an additional regression signal.

| Area | Python engine | Java engine |
| --- | --- | --- |
| Current normalization rule coverage | **More complete today** | Growing toward parity |
| DOCX advanced interoperability rules | **Reference implementation today** | Partial parity |
| XLSX advanced interoperability rules | **Reference implementation today** | Partial parity |
| PPTX advanced interoperability rules | **Reference implementation today** | Partial parity |
| Independent structural validation | Microsoft Open XML SDK | Apache POI + docx4j |
| Desktop GUI | **Tkinter portable** | Browser UI through Quarkus |
| Library integration | Python package | **Native Java JAR** |
| REST/server use | Standard-library HTTP service | **Quarkus is the more natural production server runtime** |
| Docker deployment | Supported | **Especially natural with Quarkus** |

**For maximum normalization coverage today, use the Python engine.** It currently contains the broader set of verified theme, style, table, spreadsheet and presentation portability rules.

**For Java application integration, REST services and container/server deployment, use the Java core + Quarkus.** It has a native Java API, POI/docx4j cross-parser checks and a server runtime designed for this use case.

Neither choice changes the interoperability goal: both must preserve the OOXML family, avoid editor round-trips, preserve unknown/vendor parts and converge toward the same N → normalized OOXML → N behavior. The roadmap therefore prioritizes **Java/Python rule parity plus shared regression fixtures** rather than replacing one engine with the other.

## Docker Compose: Java and Python web/API stacks

Two dedicated compose files expose the tool through a browser and REST API:

```text
docker-compose.java.yml
docker-compose.python.yml
```

Both publish **`127.0.0.1:8080` by default** and expose the same endpoint paths.

Java/Quarkus:

```bash
docker compose -f docker-compose.java.yml up --build -d
```

Python + bundled self-contained Open XML SDK validator:

```bash
docker compose -f docker-compose.python.yml up --build -d
```

Then open:

```text
http://127.0.0.1:8080/
```

Only one stack can use host port 8080 at a time. To run both simultaneously, assign a different host port to one of them, for example:

```bash
docker compose -f docker-compose.java.yml up --build -d
OOXML_PORT=8081 docker compose -f docker-compose.python.yml up --build -d
```

### Shared REST contract

Both stacks expose:

```text
GET  /api/info
POST /api/audit
POST /api/normalize?profile=interop-transitional-v1
```

For audit/normalization requests, send the raw DOCX/XLSX/PPTX as `application/octet-stream` and supply the original filename in the `X-Filename` header.

Example:

```bash
curl -f \
  -X POST \
  -H "Content-Type: application/octet-stream" \
  -H "X-Filename: document.docx" \
  --data-binary @document.docx \
  "http://127.0.0.1:8080/api/normalize?profile=interop-transitional-v1" \
  -o document-normalized.docx
```

The same HTTP client code can therefore target either engine. See [`docker/README.md`](docker/README.md) for complete `curl`, Python `urllib.request` and Java `HttpClient` examples, log handling, port overrides and CI coverage.

## Release artifact naming

Artifact names follow this rule:

```text
OOXML-Compat-Normalize-<runtime>-<variant>-<os>-<arch>.<ext>
```

A full release is expected to contain:

```text
# Python desktop
OOXML-Compat-Normalize-python-portable-win-x64.zip
OOXML-Compat-Normalize-python-portable-linux-x64.tar.gz

# Raw Java
OOXML-Compat-Normalize-java-core.jar
OOXML-Compat-Normalize-java-quarkus.jar

# Java with bundled runtime
OOXML-Compat-Normalize-java-portable-win-x64.zip
OOXML-Compat-Normalize-java-portable-linux-x64.tar.gz

# Windows Quarkus installer
OOXML-Compat-Normalize-java-quarkus-installer-win-x64.exe

SHA256SUMS.txt
```

All portable archives contain exactly one first-level directory whose name matches the archive filename without its archive extension.

## Tooling

The project deliberately separates normalization from validation and delivery:

- **Python standard library** — primary package-preserving normalization/audit engine plus lightweight local HTTP/REST service;
- **Microsoft Open XML SDK** — independent structural validation embedded in Python desktop and Python Docker builds;
- **.NET self-contained publish** — bundles that validator without requiring a .NET installation;
- **Tkinter + PyInstaller** — Python desktop GUI and one-file Windows/Linux distributions;
- **Apache POI 5.5.1** — Java cross-format OPC/OOXML parser;
- **docx4j 17.1.0** — independent Java OOXML parser/model;
- **Quarkus 3.39.3 / Quarkus REST Jackson** — local Java web/API wrapper around the Java core;
- **Maven + Maven Shade Plugin** — Java library, executable core JAR and Quarkus build;
- **Eclipse Temurin/OpenJDK 17 + jlink** — bundled Java runtime;
- **jpackage + WiX** — Windows Java app-image, `.exe` launcher and installer;
- **Docker / Docker Compose** — independent Java and Python web/API deployments;
- **CycloneDX SBOM** — Java dependency/license inventory used by CI;
- **GitHub Actions / GitHub CLI** — reproducible builds, checksums and release publication.

## Safety properties

- no LibreOffice/ONLYOFFICE/Microsoft Office editor round-trip;
- no preferred source suite and no preferred target suite;
- input and output paths must differ;
- same OOXML family on output;
- package parts are preserved unless a future explicit package-level rule owns a change;
- relationship/content-type changes are not made implicitly;
- ZIP integrity and post-flight parsing are checked;
- font substitution is disabled by default;
- risky structures are preserved + reported instead of flattened;
- local web services bind to host loopback by default; Docker requires an explicit opt-in to expose the mapped port on other interfaces.

## Development

Python:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
ooxml-compat-normalize-web
```

Java core:

```bash
mvn -f java/pom.xml clean install
```

Quarkus:

```bash
mvn -f java/pom.xml install
mvn -f quarkus/pom.xml clean verify package
```

Docker Java:

```bash
docker compose -f docker-compose.java.yml up --build -d
```

Docker Python:

```bash
docker compose -f docker-compose.python.yml up --build -d
```

## Roadmap

1. more complete Word table width/cell margin/section compatibility fixtures;
2. safe style inheritance materialization for verified Word style classes;
3. full OOXML theme color transform evaluation;
4. Excel date/locale/number-format interoperability fixtures;
5. conditional-format equivalence and drawing-anchor regression fixtures;
6. broader PowerPoint master/layout/theme/autofit regression fixtures;
7. increase Java/Python rule parity using a shared licensed/generated regression corpus;
8. optional renderer-comparison harnesses outside the core normalizer.

## License

The project source code is **MIT licensed**. Runtime/build dependencies are free/open source under their respective terms.

Python desktop/Docker builds use Microsoft Open XML SDK (MIT), .NET runtime components, Python, Tcl/Tk where applicable and PyInstaller where applicable under their respective licenses/notices.

The Java core uses **Apache POI 5.5.1** and **docx4j 17.1.0**, both Apache License 2.0, plus Maven-resolved transitive open-source dependencies. Quarkus is Apache-2.0; its transitive dependencies retain their own licenses.

Java portable distributions bundle Eclipse Temurin/OpenJDK runtime material. OpenJDK core licensing includes GPL-2.0 with the Classpath Exception, while the exact runtime distribution also carries applicable third-party licenses/notices; the runtime `legal/` material is authoritative for the shipped build.

LibreOffice, ONLYOFFICE and Microsoft Office are interoperability peers only: their binaries are not linked, invoked or redistributed. Font binaries are not bundled.

See [`LICENSE`](LICENSE), [`docs/licensing.md`](docs/licensing.md), [`docs/licensing-audit.md`](docs/licensing-audit.md), [`docs/test-corpus-policy.md`](docs/test-corpus-policy.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
