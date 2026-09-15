# Architecture

## Principle

Treat DOCX/XLSX/PPTX as OPC packages and modify only the minimum set of XML parts required by an interoperability rule.

```text
input OOXML
    |
    +-- detect family from package parts
    |
    +-- copy each ZIP entry
    |     |
    |     +-- selected XML part -> byte-local rule(s)
    |     +-- everything else   -> unchanged bytes
    |
    +-- output OOXML + JSON report
```

## Shared engine vs format-specific rules

The package engine is shared by DOCX, XLSX and PPTX. Compatibility rules are not assumed to be portable between schemas:

- WordprocessingML: `word/*.xml`
- SpreadsheetML: `xl/*.xml`
- PresentationML + DrawingML: `ppt/*.xml`

Exact font-name mapping is currently generic because font family names are represented as quoted XML attribute values in the tested cases. More complex formatting transformations must be implemented per format.

## Why not editor round-trips

Opening and re-saving a file through another office suite can reconstruct unsupported features and may alter templates, tables or other structures. This project instead treats preservation as the default and transformation as the exception.

## Rule policy

A rule should be added only when all of the following are true:

1. there is a reproducible cross-suite rendering/behavior problem;
2. the responsible OOXML representation is understood;
3. the transformation can be limited to specific parts/patterns;
4. regression tests cover both the changed and untouched content;
5. the README support matrix is updated without overstating coverage.
