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

A font inventory answers a separate question: “does this specific machine have every font required by this document?”. It does not silently redefine normalized OOXML.

## Python CLI

Audit:

```bash
ooxml-compat-normalize input.docx --audit-only --report preflight.json
```

Recommended normalization:

```bash
ooxml-compat-normalize input.docx output.docx \
  --profile interop-transitional-v1 \
  --report output.report.json
```

More explicit profile:

```bash
ooxml-compat-normalize input.pptx output.pptx \
  --profile portable-explicit-v1
```

Explicit mapping remains opt-in:

```bash
ooxml-compat-normalize input.xlsx output.xlsx \
  --font-policy map \
  --font-map 'Arial=Liberation Sans'
```

## Portable desktop application

The Tkinter GUI supports selecting one or more `.docx`, `.xlsx` or `.pptx` files, choosing the normalization profile and font policy, and writing JSON reports.

Windows/Linux portable builds embed a self-contained **.NET / Microsoft Open XML SDK** validator in the same application. End users do not need Python or .NET installed.

```text
DOCX -> DOCX
XLSX -> XLSX
PPTX -> PPTX
```

Local builds:

```powershell
# Windows x64
.\portable\build_windows_portable.ps1
```

```bash
# Linux x64
./portable/build_linux_portable.sh
```

See [`portable/README.md`](portable/README.md).

## Standalone Java JAR

For JVM environments the project also contains an **independent Java normalizer**, not a wrapper around the Python executable.

Build:

```bash
mvn -f java/pom.xml clean verify package
```

Run:

```bash
java -jar java/target/ooxml-compat-normalize-java.jar input.docx output.docx
```

Audit:

```bash
java -jar java/target/ooxml-compat-normalize-java.jar input.xlsx --audit-only
```

The Java implementation uses:

- **Apache POI 5.5.1** as a cross-format OPC/OOXML parser;
- **docx4j 17.1.0** as a second independent OOXML parser/model;
- JDK ZIP/XML primitives for the actual package-preserving writer.

POI/docx4j are deliberately used for **pre-flight and post-flight parsing/validation**, not to open and re-save the complete document. This keeps the same project rule: unknown/vendor package parts should remain untouched unless a normalization rule explicitly owns them.

The JAR currently implements the conservative package/font/semantic-color layer. Advanced `portable-explicit-v1` theme/default materialization is being ported incrementally; the Java CLI reports the partial parity rather than claiming transformations it does not yet implement.

See [`java/README.md`](java/README.md).

## Release artifacts

A release can contain all three runnable distributions:

```text
OOXML-Compat-Normalize-win-x64.zip
OOXML-Compat-Normalize-linux-x64.tar.gz
ooxml-compat-normalize-java.jar
SHA256SUMS.txt
```

The Windows/Linux binaries are desktop applications. The JAR is intended for Java/JVM workflows and requires a compatible Java runtime (Java 17+ for the project build target).

## Tooling

The project deliberately separates normalization from validation:

- **Python standard library** — main package-preserving normalization/audit engine;
- **Microsoft Open XML SDK** — independent structural validation embedded in portable desktop builds;
- **.NET self-contained publish** — bundles that validator without requiring a .NET installation;
- **Tkinter + PyInstaller** — desktop GUI and one-file Windows/Linux distributions;
- **Apache POI 5.5.1** — Java cross-format OPC/OOXML parser;
- **docx4j 17.1.0** — independent Java OOXML parser/model;
- **Maven + Maven Shade Plugin** — tested standalone Java fat JAR;
- **GitHub Actions / GitHub CLI** — reproducible Windows/Linux/JAR builds, checksums and release publication.

OpenXmlPowerTools remains a useful regression/research tool but is not a runtime dependency.

## Safety properties

- no LibreOffice/ONLYOFFICE/Microsoft Office editor round-trip;
- no preferred source suite and no preferred target suite;
- input and output paths must differ;
- same OOXML family on output;
- package parts are preserved unless a future explicit package-level rule owns a change;
- relationship/content-type changes are not made implicitly;
- ZIP integrity and post-flight parsing are checked;
- font substitution is disabled by default;
- theme materialization only occurs when unambiguous;
- risky structures are preserved + reported instead of flattened.

## Development

Python:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Java:

```bash
mvn -f java/pom.xml clean verify package
java -jar java/target/ooxml-compat-normalize-java.jar --help
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

Desktop portable builds use:

- **Microsoft Open XML SDK** — MIT;
- **.NET runtime** — MIT plus applicable third-party notices;
- **Python** — Python Software Foundation License;
- **Tcl/Tk** — permissive Tcl/Tk terms;
- **PyInstaller** — GPLv2 with the PyInstaller bootloader exception for bundled applications.

The Java JAR uses:

- **Apache POI 5.5.1** — Apache License 2.0;
- **docx4j 17.1.0** — Apache License 2.0;
- their Maven-resolved transitive open-source dependencies under their respective terms.

LibreOffice, ONLYOFFICE and Microsoft Office are interoperability peers only: their binaries are not linked, invoked or redistributed. Font binaries are not bundled; optional mappings only change OOXML family declarations when explicitly requested.

See [`LICENSE`](LICENSE), [`docs/licensing.md`](docs/licensing.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
