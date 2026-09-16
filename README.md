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

## Python CLI

```bash
ooxml-compat-normalize input.docx --audit-only --report preflight.json

ooxml-compat-normalize input.docx output.docx \
  --profile interop-transitional-v1 \
  --report output.report.json
```

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
OOXML-Compat-Normalize-Quarkus/
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

The CI explicitly tests the real `/` HTML page and the portable log location; it no longer treats `/api/info` alone as sufficient UI validation.

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

The installer adds the normal Windows launcher/shortcut while preserving the same loopback-only Quarkus behavior and file logging.

On Linux the portable contains:

```text
runtime/
OOXML-Compat-Normalize-java-core.jar
OOXML-Compat-Normalize-java-quarkus.jar
ooxml-normalize
ooxml-quarkus
LOGS.txt
logs/
```

No global Java installation is required for either portable package.

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

All artifacts in a release are built from the same commit by GitHub Actions.

## Tooling

The project deliberately separates normalization from validation and delivery:

- **Python standard library** — primary package-preserving normalization/audit engine;
- **Microsoft Open XML SDK** — independent structural validation embedded in Python desktop portable builds;
- **.NET self-contained publish** — bundles that validator without requiring a .NET installation;
- **Tkinter + PyInstaller** — Python desktop GUI and one-file Windows/Linux distributions;
- **Apache POI 5.5.1** — Java cross-format OPC/OOXML parser;
- **docx4j 17.1.0** — independent Java OOXML parser/model;
- **Quarkus 3.39.3 / Quarkus REST Jackson** — local Java web/API wrapper around the Java core;
- **Maven + Maven Shade Plugin** — Java library, executable core JAR and Quarkus build;
- **Eclipse Temurin/OpenJDK 17 + jlink** — bundled Java runtime;
- **jpackage + WiX** — Windows Java app-image, `.exe` launcher and installer;
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
- Quarkus listens only on the IPv4 loopback address by default.

## Development

Python:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
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

## Roadmap

1. more complete Word table width/cell margin/section compatibility fixtures;
2. safe style inheritance materialization for verified Word style classes;
3. full OOXML theme color transform evaluation;
4. Excel date/locale/number-format interoperability fixtures;
5. conditional-format equivalence and drawing-anchor regression fixtures;
6. broader PowerPoint master/layout/theme/autofit regression fixtures;
7. increase Java/Python rule parity;
8. optional renderer-comparison harnesses outside the core normalizer.

## License

The project source code is **MIT licensed**. Runtime/build dependencies are free/open source.

Python desktop portable builds use Microsoft Open XML SDK (MIT), .NET, Python, Tcl/Tk and PyInstaller under their respective licenses.

The Java core uses **Apache POI 5.5.1** and **docx4j 17.1.0**, both Apache License 2.0, plus their Maven-resolved transitive open-source dependencies.

The Quarkus local service uses **Quarkus 3.39.3**, licensed under Apache License 2.0, plus compatible open-source dependencies.

Java portable distributions bundle a runtime derived from **Eclipse Temurin/OpenJDK 17**. OpenJDK is distributed under **GPL-2.0 with the Classpath Exception**, plus the applicable third-party notices. This does not change the MIT license of this project's source code, but the runtime's license/notices travel with the portable distribution.

LibreOffice, ONLYOFFICE and Microsoft Office are interoperability peers only: their binaries are not linked, invoked or redistributed. Font binaries are not bundled.

See [`LICENSE`](LICENSE), [`docs/licensing.md`](docs/licensing.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
