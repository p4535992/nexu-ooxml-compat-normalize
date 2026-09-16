# Architecture

## Core invariant

**Preservation is the default; transformation is the exception.**

```text
OOXML package
   |
   +-- preflight analyzer
   |      +-- family / producer / conformance
   |      +-- fonts / themes / styles
   |      +-- DOCX/XLSX/PPTX-specific diagnostics
   |      +-- portability risks
   |
   +-- canonical profile
   |      +-- preserve-v1
   |      +-- interop-transitional-v1
   |      +-- portable-explicit-v1
   |
   +-- schema-specific rule layer
   |      +-- WordprocessingML
   |      +-- SpreadsheetML
   |      +-- PresentationML / DrawingML
   |
   +-- OPC package writer
   |
   +-- preservation verifier
   |      +-- same part set
   |      +-- relationships unchanged
   |      +-- content types unchanged
   |      +-- ZIP integrity
   |
   +-- postflight analyzer
```

## Rule classes

Rules fall into three categories:

1. **Normalize**: a proven non-portable representation has a semantically safer standard representation.
2. **Materialize**: an implicit/theme-dependent value can be resolved without ambiguity, making renderer input more explicit.
3. **Audit only**: rewriting could alter author semantics, so the current engine reports it instead.

### Current normalize/materialize examples

- color-semantic glyphs -> ordinary glyph + explicit OOXML color;
- theme font placeholders -> concrete typefaces when package-wide resolution is unambiguous;
- simple theme color references -> explicit RGB when no unsupported transforms are present;
- Word implicit table layout default -> explicit `autofit`;
- Excel `twoCellAnchor` implicit `editAs` -> explicit `twoCell`.

### Current audit-only examples

- Word missing/cyclic `basedOn` style inheritance;
- duplicate/missing Excel custom number formats;
- duplicate Excel conditional-format priorities;
- PowerPoint text bodies relying on implicit autofit;
- high-risk OLE/ActiveX/external/altChunk features.

## Why package-wide theme resolution can be intentionally incomplete

PowerPoint can contain multiple masters/themes. Applying the first theme to every slide would be destructive. The current engine merges only theme values that are identical across every parsed theme; conflicting values remain theme-dependent and are not materialized. A future PPTX resolver can walk slide -> layout -> master -> theme relationships per slide.

## Why no editor round-trip

Office applications import OOXML into proprietary in-memory models and export it again. Unsupported or partially-supported content can be reconstructed, flattened or dropped. The core engine therefore performs package-local transformations and reserves renderer-based comparison for an optional external QA harness.
