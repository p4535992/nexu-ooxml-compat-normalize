# ooxml-compat-normalize

Loss-averse OOXML interoperability normalizer for **DOCX, XLSX and PPTX**.

The repository name is historical: the engine is OOXML-wide. It targets documents exchanged between LibreOffice, ONLYOFFICE, Microsoft Office and other OOXML consumers **without opening and re-saving the file in another office editor**.

The normalizer treats every Office file as an OPC/ZIP package, performs a preflight audit, applies only narrowly-scoped rules, preserves unknown content, verifies package invariants, then performs a postflight audit.

## Goal

Create a practical common OOXML representation that minimizes cross-suite drift while preserving as much author intent as possible:

- fonts and font intent;
- direct and theme colors;
- Word/Excel/PowerPoint styles;
- tables, cells, shapes and drawing anchors;
- themes and inheritance;
- images/media;
- relationships and content types;
- headers, footers, notes and auxiliary parts;
- unknown/vendor parts unless a rule explicitly owns them.

No tool can promise pixel-identical rendering across every office suite, because installed font files, shaping engines and vendor-specific features remain environment-dependent. The project therefore supports **audit/report**, conservative normalization and fail-closed **strict mode** rather than silently flattening unsupported content.

## Profiles

The output always remains in the **same OOXML family**: DOCX -> DOCX, XLSX -> XLSX, PPTX -> PPTX. The profiles control how much is made explicit.

| Profile | Purpose |
| --- | --- |
| `preserve-v1` | Preserve package semantics; useful for audit/copy workflows and explicit user font mappings. |
| `interop-transitional-v1` | Recommended conservative cross-suite profile; normalizes proven renderer-dependent constructs while preserving themes/defaults. |
| `portable-explicit-v1` | Additionally materializes theme fonts/colors where unambiguous and safe implicit defaults supported by the engine. |

`portable-explicit-v1` currently materializes only transformations the project can express without reconstructing the whole document model. Ambiguous theme color transforms, complex inheritance and high-risk vendor features remain preserved + reported.

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
```

The pre-flight combines the project's loss-averse package audit with an optional/embedded **Open XML SDK** structural validation. The format-specific engine then applies only narrowly-scoped transformations. Post-flight repeats package checks and Open XML SDK validation so a portable build can detect structural regressions instead of silently shipping them.

## What is implemented

| Area | DOCX | XLSX | PPTX |
| --- | --- | --- | --- |
| Package-preserving copy + ZIP verification | ✅ | ✅ | ✅ |
| Producer/conformance/font/risk preflight | ✅ | ✅ | ✅ |
| Exact font mapping in real font declarations | ✅ | ✅ | ✅ |
| Font inventory validation | ✅ | ✅ | ✅ |
| Renderer-dependent color symbols -> explicit OOXML color | ✅ simple runs | ✅ rich-text runs | ✅ simple DrawingML runs |
| Theme-font materialization (`portable-explicit-v1`) | ✅ `w:rFonts` | ✅ styles + DrawingML | ✅ DrawingML placeholders |
| Theme-color materialization without tint/shade transforms | ✅ | ✅ | ✅ |
| Word implicit table layout -> explicit `autofit` | ✅ | — | — |
| Word style inheritance diagnostics | ✅ missing parents/cycles | — | — |
| Excel custom number-format diagnostics | — | ✅ duplicate/missing IDs | — |
| Excel conditional-format priority diagnostics | — | ✅ | — |
| Excel `twoCellAnchor` default -> explicit `editAs="twoCell"` | — | ✅ | — |
| PowerPoint master/layout inventory | — | — | ✅ |
| PowerPoint implicit text-autofit diagnostics | — | — | ✅ |
| Unknown/vendor parts preserved | ✅ | ✅ | ✅ |
| Strict OOXML -> Transitional conversion | planned | planned | planned |

### Why some items are diagnostics only

Examples such as Word style inheritance, Excel conditional-format ordering and PowerPoint autofit can affect layout or precedence. The project will not automatically rewrite them until a transformation has a verified semantic equivalence and regression fixtures. **Reporting a risky construct is preferable to silently changing it.**

## Theme materialization

`portable-explicit-v1` can remove some renderer dependence while keeping the original package structure:

- Word theme font references such as `minorHAnsi` are resolved to the actual theme family in `w:rFonts`;
- DrawingML placeholders such as `+mn-lt` are replaced with the theme's concrete latin font;
- SpreadsheetML major/minor scheme fonts are materialized in `xl/styles.xml`;
- simple theme colors with no tint/shade/luminance transforms are converted to explicit RGB/sRGB;
- transformed/ambiguous theme colors are preserved and left for later rules.

This is intentionally different from a global XML string replacement.

## Font strategy

Font files are external dependencies of the renderer. The default is therefore **preserve the original family names and inventory them**.

Audit:

```bash
ooxml-compat-normalize input.docx --audit-only --report preflight.json
```

Verify a target renderer has every required family:

```bash
ooxml-compat-normalize input.docx output.docx \
  --strict \
  --font-policy require-available \
  --font-inventory target-fonts.txt
```

Explicit mapping is opt-in:

```bash
ooxml-compat-normalize input.pptx output.pptx \
  --font-policy map \
  --font-map 'Arial=Liberation Sans'
```

Convenience mappings are available:

```bash
ooxml-compat-normalize input.xlsx output.xlsx --font-profile liberation
```

The mapper touches only OOXML locations that declare font families; it never rewrites user-visible text containing the same words.

## CLI usage

Recommended conservative profile:

```bash
ooxml-compat-normalize input.docx output.docx \
  --profile interop-transitional-v1 \
  --report output.report.json
```

More explicit portable profile:

```bash
ooxml-compat-normalize input.pptx output.pptx \
  --profile portable-explicit-v1 \
  --report output.report.json
```

Preservation-oriented pass:

```bash
ooxml-compat-normalize input.xlsx output.xlsx --profile preserve-v1
```

## Portable GUI

A small Tkinter GUI supports selecting one or more `.docx`, `.xlsx` or `.pptx` files, selecting the normalization profile, optionally applying explicit font mappings and writing JSON reports.

The portable build embeds a self-contained **.NET 8 / Open XML SDK validator** inside the same one-file application. End users therefore do not need Python or .NET installed.

The GUI always exports to the **same OOXML family**:

```text
DOCX -> DOCX
XLSX -> XLSX
PPTX -> PPTX
```

It does not claim that DOCX -> XLSX or PPTX -> DOCX is a safe interoperability conversion.

Local builds:

```powershell
# Windows x64
.\portable\build_windows_portable.ps1
```

```bash
# Linux x64
./portable/build_linux_portable.sh
```

GitHub Actions builds both platform executables and can attach them to a GitHub Release. See [`portable/README.md`](portable/README.md).

## Tooling

The project deliberately separates normalization from validation:

- **Python standard library** (`zipfile`, XML/parsing utilities, hashing): package-preserving normalization and audit logic;
- **Microsoft Open XML SDK**: independent DOCX/XLSX/PPTX schema/model validation before and after normalization;
- **.NET 8 self-contained publish**: produces the validator helper without requiring a .NET installation on the end-user machine;
- **Tkinter**: minimal desktop GUI for selecting files and profiles;
- **PyInstaller**: build tool that bundles the Python GUI/engine and the self-contained .NET validator into one portable executable per operating system;
- **GitHub Actions / GitHub CLI**: reproducible Windows/Linux builds, checksums and release publication.

OpenXmlPowerTools, Apache POI and docx4j are useful candidates for additional regression/cross-parser testing, but they are **not runtime dependencies** at this stage. The core normalizer avoids high-level editor round-trips so unknown/vendor OOXML parts can remain untouched.

## Strict mode

Strict mode is intended for publishing pipelines where unresolved portability must stop the build. It can reject:

- unsupported Strict -> Transitional conversion;
- missing target fonts when a font inventory is supplied/required;
- high-risk constructs such as `altChunk`, ActiveX, embedded OLE/packages or external links;
- style inheritance cycles and other high-risk format diagnostics;
- semantic-color symbols that remain because transforming the containing run would be destructive.

## Safety properties

- no LibreOffice/ONLYOFFICE/Microsoft Office editor round-trip;
- input and output paths must differ;
- same package part set after writing;
- relationship parts unchanged unless a future rule explicitly owns them;
- `[Content_Types].xml` unchanged unless a future rule explicitly owns it;
- ZIP integrity verified;
- postflight analysis always reruns;
- theme materialization only when a value is unambiguous;
- theme colors carrying unsupported transforms remain untouched;
- risky structures are preserved + reported instead of flattened.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

The normalization engine uses the Python standard library; portable builds additionally bundle the self-contained Open XML SDK validator.

## Roadmap

The next major rules are expected to focus on:

1. more complete Word table width/cell margin/section compatibility fixtures;
2. safe style inheritance materialization for verified Word style classes;
3. full OOXML theme color transform evaluation (tint/shade/luminance/alpha);
4. Excel date/locale/number-format interoperability fixtures;
5. conditional-format equivalence checks and drawing-anchor regression fixtures;
6. PowerPoint master/layout resolution per slide rather than only package-wide unambiguous theme values;
7. PowerPoint autofit/text metric regression rules;
8. optional renderer-comparison harnesses outside the core normalizer.

## License

The project source code is **MIT licensed**. The portable distribution is intentionally built only from free/open-source components:

- **Microsoft Open XML SDK** — MIT;
- **.NET runtime** — MIT and associated third-party notices;
- **Python** — Python Software Foundation License;
- **Tcl/Tk / Tkinter runtime components** — permissive Tcl/Tk license terms;
- **PyInstaller** — GPLv2 with the PyInstaller bootloader exception that permits distributing bundled applications under the application's own license.

LibreOffice, ONLYOFFICE and Microsoft Office are interoperability targets only: their binaries are not linked, invoked or redistributed by the normalizer. Fonts are not bundled; optional font mappings only change OOXML family names.

See [`LICENSE`](LICENSE), [`docs/licensing.md`](docs/licensing.md) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
