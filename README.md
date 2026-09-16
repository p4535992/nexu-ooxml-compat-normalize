# ooxml-compat-normalize

Loss-averse OOXML interoperability normalizer for **DOCX, XLSX and PPTX**.

The project is intentionally **not** a LibreOffice -> ONLYOFFICE converter, nor an ONLYOFFICE -> LibreOffice converter. Its goal is to normalize documents produced by LibreOffice, ONLYOFFICE, Microsoft Office and other OOXML consumers toward a **common, explicit and cross-suite OOXML representation** that can then be consumed again by any of those applications.

Conceptually, the project is **N -> 1 -> N**:

```text
LibreOffice ----┐                         ┌---- LibreOffice
ONLYOFFICE -----┤                         ├---- ONLYOFFICE
Microsoft Office├--> normalized OOXML --->├---- Microsoft Office
other OOXML ----┘                         └---- other OOXML
```

There is no preferred source suite and no preferred target suite. Normalization should be as symmetric as possible: the same normalized DOCX/XLSX/PPTX should remain useful when moving in either direction between applications.

The normalizer treats every Office file as an OPC/ZIP package, performs a pre-flight audit, applies only narrowly-scoped rules, preserves unknown content, verifies package invariants, then performs a post-flight audit. It does **not** open and re-save the document through another office editor.

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

The preferred transformation is not "make LibreOffice output look like ONLYOFFICE" or the reverse. The preferred transformation is:

```text
source semantics
      ↓
resolve only safe/known OOXML ambiguity
      ↓
explicit, standard OOXML semantics
      ↓
LibreOffice / ONLYOFFICE / Microsoft Office / other consumers
```

No tool can promise pixel-identical rendering across every office suite because installed font files, shaping engines, layout engines and vendor-specific features remain environment-dependent. The project therefore supports **audit/report**, conservative normalization and fail-closed **strict mode** rather than silently flattening unsupported content.

## Profiles

The output always remains in the **same OOXML family**: DOCX -> DOCX, XLSX -> XLSX, PPTX -> PPTX. The profiles control how much implicit OOXML meaning is made explicit.

| Profile | Purpose |
| --- | --- |
| `preserve-v1` | Preserve package semantics; useful for audit/copy workflows and explicit user mappings. |
| `interop-transitional-v1` | Recommended conservative cross-suite profile; normalizes proven renderer-dependent constructs while preserving safe semantics. |
| `portable-explicit-v1` | Additionally materializes theme fonts/colors and safe implicit defaults where the result is unambiguous. |

`portable-explicit-v1` currently materializes only transformations the project can express without reconstructing the whole document model. Ambiguous theme transforms, complex inheritance and high-risk vendor features remain preserved + reported.

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

The pre-flight combines the project's loss-averse package audit with an optional/embedded **Open XML SDK** structural validation. The format-specific engine then applies only narrowly-scoped transformations. Post-flight repeats package checks and Open XML SDK validation so a portable build can detect structural regressions instead of silently shipping them.

The normalized file has **no target-application flag**. LibreOffice, ONLYOFFICE and Microsoft Office are peers in the interoperability model.

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
| PowerPoint slide/layout/master/theme inheritance resolution | — | — | ✅ |
| PowerPoint implicit text-autofit diagnostics | — | — | ✅ |
| Unknown/vendor parts preserved | ✅ | ✅ | ✅ |
| Strict OOXML -> Transitional conversion | planned | planned | planned |

### Why some items are diagnostics only

Examples such as Word style inheritance, Excel conditional-format ordering and PowerPoint autofit can affect layout or precedence. The project will not automatically rewrite them until a transformation has a verified semantic equivalence and regression fixtures. **Reporting a risky construct is preferable to silently changing it.**

## Theme materialization

`portable-explicit-v1` can remove some renderer dependence while keeping the original package structure:

- Word theme font references such as `minorHAnsi` can be resolved to the actual theme family in `w:rFonts`;
- DrawingML placeholders such as `+mn-lt` can be replaced with the theme's concrete latin font;
- SpreadsheetML major/minor scheme fonts can be materialized in `xl/styles.xml`;
- simple theme colors with no tint/shade/luminance transforms can become explicit RGB/sRGB;
- transformed/ambiguous theme colors remain preserved for later rules.

The purpose is to make the **same semantic value more explicit**, not to replace it with a suite-specific value. If a theme resolves to `Carlito`, materialization should produce explicit `Carlito`, not a font chosen for one particular application.

This is intentionally different from a global XML string replacement.

## Font strategy

Font handling follows the same N -> 1 -> N interoperability principle. There is **no default target suite**.

The default behavior is **preserve font identity and semantics**:

- keep explicitly declared font family names unchanged;
- resolve theme/font inheritance only when the result is unambiguous and the selected profile calls for it;
- never substitute a family merely because another suite might prefer a different one;
- inventory required fonts and report environment dependencies separately from document normalization.

This is the safest default for documents coming from **either LibreOffice or ONLYOFFICE** and going back to **either LibreOffice or ONLYOFFICE**, as well as Microsoft Office and other OOXML consumers.

### GUI font modes

The portable GUI exposes font handling as an explicit dropdown:

| Mode | Behavior |
| --- | --- |
| **Preserva esattamente i font originali** | **Default.** No automatic family substitution. Keeps the document's declared font identities. |
| **Sostituisci solo i font mancanti** | Preserves every source font available on the current machine; for a missing family, uses a known metric-compatible fallback only when that fallback is installed. |
| **Forza profilo compatibile** | Explicit opt-in mapping for known Microsoft-compatible families, e.g. Arial -> Liberation Sans, Calibri -> Carlito. |
| **Mapping personalizzato** | User-defined `OLD=NEW` mappings, optionally restricted to missing source fonts. |

The last three modes are **environment/user policy**, not part of the canonical default representation.

### Font inventory is verification, not normalization policy

A font inventory answers a separate question:

```text
Does this machine / renderer have every font required by this document?
```

It should not silently redefine the canonical OOXML representation.

Audit:

```bash
ooxml-compat-normalize input.docx --audit-only --report preflight.json
```

Verify a particular environment has every required family:

```bash
ooxml-compat-normalize input.docx output.docx \
  --strict \
  --font-policy require-available \
  --font-inventory environment-fonts.txt
```

Explicit mapping remains opt-in:

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

A small Tkinter GUI supports selecting one or more `.docx`, `.xlsx` or `.pptx` files, selecting the normalization profile, choosing the font policy and writing JSON reports.

The portable build embeds a self-contained **.NET 8 / Open XML SDK validator** inside the same one-file application. End users therefore do not need Python or .NET installed.

The GUI always exports to the **same OOXML family**:

```text
DOCX -> DOCX
XLSX -> XLSX
PPTX -> PPTX
```

This is not a one-way application conversion. A normalized DOCX may originate from LibreOffice and be opened in ONLYOFFICE, originate from ONLYOFFICE and be opened in LibreOffice, or continue through Microsoft Office and other OOXML consumers.

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
- missing environment fonts when a font inventory is supplied/required;
- high-risk constructs such as `altChunk`, ActiveX, embedded OLE/packages or external links;
- style inheritance cycles and other high-risk format diagnostics;
- semantic-color symbols that remain because transforming the containing run would be destructive.

## Safety properties

- no LibreOffice/ONLYOFFICE/Microsoft Office editor round-trip;
- no preferred source suite and no preferred target suite;
- input and output paths must differ;
- same OOXML family on output;
- same package part set after writing unless a future explicit rule owns a package-level change;
- relationship parts unchanged unless a future rule explicitly owns them;
- `[Content_Types].xml` unchanged unless a future rule explicitly owns it;
- ZIP integrity verified;
- postflight analysis always reruns;
- font substitution disabled by default;
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
6. broader PowerPoint master/layout/theme inheritance regression fixtures;
7. PowerPoint autofit/text metric regression rules;
8. optional renderer-comparison harnesses outside the core normalizer.

## License

The project source code is **MIT licensed**. The portable distribution is intentionally built only from free/open-source components:

- **Microsoft Open XML SDK** — MIT;
- **.NET runtime** — MIT and associated third-party notices;
- **Python** — Python Software Foundation License;
- **Tcl/Tk / Tkinter runtime components** — permissive Tcl/Tk license terms;
- **PyInstaller** — GPLv2 with the PyInstaller bootloader exception that permits distributing bundled applications under the application's own license.

LibreOffice, ONLYOFFICE and Microsoft Office are interoperability peers/targets only: their binaries are not linked, invoked or redistributed by the normalizer. Fonts are not bundled; optional font mappings only change OOXML family names when the user explicitly requests such a policy.

See [`LICENSE`](LICENSE), [`docs/licensing.md`](docs/licensing.md) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
