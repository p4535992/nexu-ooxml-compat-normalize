# docx-compat-normalizer

Loss-averse OOXML interoperability normalizer for **DOCX, XLSX and PPTX**.

The project is designed to improve document portability between **LibreOffice, ONLYOFFICE, Microsoft Office and other OOXML-compatible applications** by normalizing selected interoperability-sensitive structures while preserving the original package as much as possible.

The goal is not to rebuild a document through a different office editor. Instead, the normalizer works directly on the OOXML package, audits it before conversion, applies narrowly-scoped compatibility rules, and verifies the result afterwards.

> The repository name is historical: the project targets the three main OOXML document families, not only DOCX.

## Goal

The normalizer tries to reduce cross-suite differences while preserving, whenever possible:

- fonts and font intent;
- explicit colors and theme colors;
- paragraph, cell and shape styles;
- tables and layout properties;
- numbering and lists;
- themes and inheritance;
- images, drawings and media;
- headers, footers, notes and auxiliary parts;
- relationships and content types;
- unsupported or unknown OOXML parts that do not need to be changed.

No tool can guarantee pixel-identical rendering in every office suite because renderers, installed fonts and implementation-specific behavior can differ. The project therefore follows a **loss-averse** approach: preserve what is already valid, normalize only what can be handled safely, and report situations that cannot be guaranteed instead of silently flattening content.

## Architecture

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

The pre-flight phase inventories the document before any modification. The format-specific normalizer then applies only compatible transformations for WordprocessingML, SpreadsheetML or PresentationML/DrawingML. The post-flight phase verifies package integrity and checks that required parts and relationships have not disappeared.

## Current direction

The project is intended to become a common normalization layer for documents produced by different office suites.

Important interoperability areas include:

- font inventory, fallback and explicit font mapping;
- theme fonts and theme colors;
- semantic colors that depend on renderer-specific emoji support;
- Word tables, autofit, sections and style inheritance;
- Excel number formats, rich text, conditional formatting and drawing anchors;
- PowerPoint master/layout/theme inheritance, placeholders and text autofit;
- OOXML Strict/Transitional compatibility;
- suite-specific producer fingerprints;
- preservation of unknown package parts and relationships;
- pre-flight and post-flight validation.

Rules are intentionally format-specific. A safe DOCX transformation is not automatically assumed to be safe for XLSX or PPTX.

## Current implementation

| Capability | DOCX | XLSX | PPTX |
| --- | --- | --- | --- |
| Package-preserving OOXML copy | ✅ | ✅ | ✅ |
| Format detection | ✅ | ✅ | ✅ |
| Exact font-name mapping | ✅ | experimental | experimental |
| Selected semantic-color normalization | ✅ | planned / experimental | planned / experimental |
| LibreOffice / ONLYOFFICE editor round-trip | **never** | **never** | **never** |

The project evolves through real interoperability fixtures and regression tests. Features are only considered supported when a format-specific rule can preserve the rest of the package and can be verified afterwards.

## Why direct OOXML normalization

DOCX, XLSX and PPTX are OPC/ZIP packages containing XML parts, relationships, media and other resources.

Instead of performing:

```text
LibreOffice file -> open in another editor -> save again
```

the project aims for:

```text
OOXML package
    -> inspect
    -> modify only selected compatibility-sensitive markup
    -> preserve the remaining package
    -> verify output
```

This reduces the risk of losing templates, tables, unsupported extensions, drawings or other structures just because another editor imported and re-exported the document.

## Font strategy

Font availability is one of the largest causes of cross-suite layout drift.

The preferred behavior is to **preserve the original font declaration** and inventory the fonts required by the document. Explicit font mapping should only be used when the target environment is known not to contain the original font.

A convenience mapping can use metric-compatible families such as Liberation fonts, but mappings are opt-in because changing a font family is a semantic document change.

Example:

```bash
ooxml-compat-normalize input.docx output.docx \
  --font-profile liberation \
  --report normalization-report.json
```

## Usage

Install the Python package:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Basic normalization:

```bash
ooxml-compat-normalize input.docx output.docx
```

Custom exact font mapping:

```bash
ooxml-compat-normalize input.pptx output.pptx \
  --font-map 'Arial=Liberation Sans'
```

The input and output remain in the same document family: DOCX stays DOCX, XLSX stays XLSX and PPTX stays PPTX. The project is a compatibility normalizer, not a semantic DOCX-to-XLSX or PPTX-to-DOCX converter.

## Safety principles

- input and output are separate files;
- office documents are not opened and re-saved through LibreOffice, ONLYOFFICE or Microsoft Office;
- unmodified package entries are preserved whenever possible;
- transformations are limited to known OOXML structures;
- relationships and content types are preservation targets;
- unsupported structures should be reported instead of silently flattened;
- normalization should be followed by a post-flight verification step;
- a compatibility rule must not globally replace arbitrary text inside XML.

## Tooling

The project intentionally keeps the core lightweight.

- **Python 3** — implementation language.
- **Python standard library** — ZIP/OPC package handling, XML/text processing, hashing and CLI support; the core is designed to avoid mandatory heavy runtime dependencies.
- **Tkinter** — lightweight graphical interface for the portable desktop application.
- **PyInstaller** — used only at build time to create standalone Windows and Linux executables; it is not required by the normalizer runtime when installed as a Python package.
- **GitHub Actions** — intended to build and publish reproducible portable binaries for supported platforms.

LibreOffice, ONLYOFFICE and Microsoft Office are **compatibility targets**, not bundled conversion engines.

The project does not bundle Open XML SDK, OpenXmlPowerTools, office suites, proprietary Microsoft fonts or font binaries.

## Testing

```bash
python -m unittest discover -s tests -v
```

Regression tests should use synthetic fixtures or documents whose redistribution is permitted. Real interoperability failures should be reduced to focused fixtures whenever possible.

## Scope and limitations

This project is not an OOXML renderer and cannot promise identical pagination or pixel output on every office suite and operating system.

Its objective is narrower and testable: **reduce avoidable OOXML interoperability differences without unnecessarily rebuilding the document**.

Complex features such as embedded objects, ActiveX, macros, SmartArt, external links, proprietary extensions or unsupported renderer behavior may need to be preserved and reported rather than transformed.

## License

The source code of **docx-compat-normalizer** is released under the **MIT License**. See [`LICENSE`](LICENSE).

The project does not redistribute LibreOffice, ONLYOFFICE, Microsoft Office, Microsoft proprietary fonts or other office-suite binaries. References to third-party font families or office applications are interoperability references only unless explicitly stated otherwise.

Build-time tooling such as PyInstaller keeps its own upstream license and is not incorporated into the project source license merely because it is used to produce an executable. Any future third-party dependency or redistributed component must be documented separately in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and, where applicable, in [`docs/licensing.md`](docs/licensing.md).
