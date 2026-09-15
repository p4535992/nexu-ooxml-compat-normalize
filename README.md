# docx-compat-normalizer

Conservative OOXML normalizer for improving interoperability between LibreOffice, ONLYOFFICE and Microsoft Office **without opening and re-saving documents in another office editor**.

The project was started from a real interoperability case where a DOCX created by LibreOffice changed fonts in ONLYOFFICE and Unicode color-circle emoji (`🔴 🟡 🟠 🟢`) became monochrome.

## Why this approach

DOCX, XLSX and PPTX are OPC/ZIP packages containing OOXML parts. Instead of rebuilding the whole document through a high-level office library, this tool copies the package entry-by-entry and changes only explicitly selected XML bytes.

That design is intentional: tables, templates, relationships, images and unsupported structures are left untouched unless a rule explicitly targets them.

## Current status

| Capability | DOCX | XLSX | PPTX |
| --- | --- | --- | --- |
| Package-preserving copy | ✅ | ✅ | ✅ |
| Exact font-name mapping in XML | ✅ | ✅ experimental | ✅ experimental |
| `🔴 🟡 🟠 🟢` -> explicit OOXML color | ✅ | not implemented | not implemented |
| LibreOffice/ONLYOFFICE editor round-trip | **never** | **never** | **never** |

The architecture is therefore valid for all three OOXML families, but **normalization rules are format-specific**. DOCX currently has the most complete rule set because it is the format tested against the original problem.

## Implemented compatibility fixes

### DOCX color circles

Simple emoji runs such as:

```xml
<w:r><w:rPr></w:rPr><w:t xml:space="preserve">🔴 </w:t></w:r>
```

are conservatively changed to an ordinary circle glyph plus an explicit OOXML color and font. This removes dependency on the office application's color-emoji fallback.

### Optional font mapping

The built-in `liberation` profile maps the fonts observed in the original compatibility case:

- `Times New Roman` -> `Liberation Serif`
- `Arial` -> `Liberation Sans`
- `Courier New` -> `Liberation Mono`

The profile is **opt-in** because renaming fonts is a semantic document change. If the target ONLYOFFICE installation already has the original fonts, prefer preserving them.

## Installation

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e .
```

There are no runtime Python dependencies outside the standard library.

## Usage

Preserve fonts, fix supported DOCX color circles:

```bash
ooxml-compat-normalize input.docx output.docx
```

Normalize color circles and map the tested Microsoft core fonts to Liberation fonts:

```bash
ooxml-compat-normalize input.docx output.docx \
  --font-profile liberation \
  --report normalization-report.json
```

Use a custom exact font mapping:

```bash
ooxml-compat-normalize input.pptx output.pptx \
  --font-map 'Arial=Liberation Sans'
```

XLSX/PPTX currently use only the package-preserving font mapping layer. Their emoji/color normalization needs format-specific DrawingML/SpreadsheetML rules and is intentionally not claimed as implemented yet.

## Safety properties

- input and output must be different paths; in-place editing is disabled;
- unmodified ZIP entries are copied with their original `ZipInfo` metadata;
- XML is patched byte-locally instead of parsed and re-serialized wholesale;
- exact quoted font values are replaced, so `Arial` does not modify `Arial Unicode MS`;
- DOCX runs with existing non-empty run properties are skipped by the color-circle rule;
- every run produces a JSON report containing changed parts and before/after SHA-256 hashes.

## Testing

```bash
python -m unittest discover -s tests -v
```

The tests generate synthetic OOXML packages and do not embed user documents.

## Scope and non-goals

This is not a generic OOXML repair engine and does not promise pixel-identical rendering between office suites. It focuses on small, auditable compatibility transformations that can be proven necessary by a real document.

It does **not** bundle or invoke LibreOffice, ONLYOFFICE, Microsoft Office, Open XML SDK, OpenXmlPowerTools, or office fonts.

## License

MIT. See [LICENSE](LICENSE) and [docs/licensing.md](docs/licensing.md).
