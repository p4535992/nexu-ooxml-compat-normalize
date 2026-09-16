from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from xml.etree import ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from .package import DocumentKind, detect_document_kind


TRANSITIONAL_MARKERS = (
    b"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    b"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    b"http://schemas.openxmlformats.org/presentationml/2006/main",
)
STRICT_MARKERS = (
    b"http://purl.oclc.org/ooxml/wordprocessingml/main",
    b"http://purl.oclc.org/ooxml/spreadsheetml/main",
    b"http://purl.oclc.org/ooxml/presentationml/main",
)

# Unicode characters whose *encoded character* carries a named color semantic.
# Color-font rendering is implementation-dependent, therefore these are candidates
# for conversion to an ordinary geometric glyph plus an explicit OOXML color.
SEMANTIC_COLOR_SYMBOLS: dict[str, tuple[str, str, str]] = {
    "🔴": ("circle", "●", "FF0000"),
    "🟠": ("circle", "●", "ED7D31"),
    "🟡": ("circle", "●", "FFC000"),
    "🟢": ("circle", "●", "00B050"),
    "🔵": ("circle", "●", "4472C4"),
    "🟣": ("circle", "●", "7030A0"),
    "🟤": ("circle", "●", "8B4513"),
    "⚫": ("circle", "●", "000000"),
    "⚪": ("circle", "●", "FFFFFF"),
    "🟥": ("square", "■", "FF0000"),
    "🟧": ("square", "■", "ED7D31"),
    "🟨": ("square", "■", "FFC000"),
    "🟩": ("square", "■", "00B050"),
    "🟦": ("square", "■", "4472C4"),
    "🟪": ("square", "■", "7030A0"),
    "🟫": ("square", "■", "8B4513"),
    "⬛": ("square", "■", "000000"),
    "⬜": ("square", "■", "FFFFFF"),
}


@dataclass(frozen=True)
class Risk:
    code: str
    severity: str
    message: str
    part: str | None = None


@dataclass(frozen=True)
class PackageAnalysis:
    path: str
    document_kind: str
    producer: str | None
    conformance: str
    entry_count: int
    xml_part_count: int
    relationship_part_count: int
    required_fonts: tuple[str, ...]
    semantic_color_symbols: dict[str, int]
    has_theme: bool
    style_parts: tuple[str, ...]
    risks: tuple[Risk, ...]
    diagnostics: dict[str, object]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["risks"] = [asdict(r) for r in self.risks]
        return data


def _decode_xml(data: bytes) -> str:
    # OOXML XML is overwhelmingly UTF-8/UTF-16. For analysis, replacement is safer
    # than rejecting the entire package due to one malformed declaration.
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def _extract_application(app_xml: bytes) -> str | None:
    text = _decode_xml(app_xml)
    match = re.search(r"<(?:\w+:)?Application>(.*?)</(?:\w+:)?Application>", text, re.S)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip() or None
    return None


def _extract_fonts(kind: DocumentKind, part: str, data: bytes) -> set[str]:
    text = _decode_xml(data)
    fonts: set[str] = set()

    # WordprocessingML run fonts. Restrict attribute parsing to <w:rFonts>;
    # attributes such as w:lang/@w:eastAsia contain language tags, not font names.
    if kind is DocumentKind.DOCX and part.startswith("word/"):
        for tag_match in re.finditer(r"<(?:\w+:)?rFonts\b[^>]*>", text):
            tag = tag_match.group(0)
            for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                for match in re.finditer(rf"(?:\w+:)?{attr}=\"([^\"]+)\"", tag):
                    fonts.add(match.group(1))
        if part == "word/fontTable.xml":
            for match in re.finditer(r"<(?:\w+:)?font\b[^>]*\b(?:\w+:)?name=\"([^\"]+)\"", text):
                fonts.add(match.group(1))

    # DrawingML theme/run fonts used heavily by PPTX and also by charts/shapes in
    # DOCX/XLSX. Empty typefaces and theme placeholders (+mj-lt etc.) are not files.
    for match in re.finditer(r"typeface=\"([^\"]+)\"", text):
        value = match.group(1).strip()
        if value and not value.startswith("+"):
            fonts.add(value)

    # SpreadsheetML styles/rich text.
    if kind is DocumentKind.XLSX:
        if part == "xl/styles.xml":
            for match in re.finditer(r"<(?:\w+:)?name\b[^>]*\bval=\"([^\"]+)\"", text):
                fonts.add(match.group(1))
        for match in re.finditer(r"<(?:\w+:)?rFont\b[^>]*\bval=\"([^\"]+)\"", text):
            fonts.add(match.group(1))

    return fonts


def _detect_conformance(xml_parts: list[bytes]) -> str:
    sample = b"\n".join(xml_parts[:16])
    if any(marker in sample for marker in STRICT_MARKERS):
        return "strict"
    if any(marker in sample for marker in TRANSITIONAL_MARKERS):
        return "transitional"
    return "unknown"


def _risk_scan(names: set[str], xml_by_name: dict[str, bytes]) -> list[Risk]:
    risks: list[Risk] = []

    def add(code: str, severity: str, message: str, part: str | None = None) -> None:
        risks.append(Risk(code, severity, message, part))

    for name in sorted(names):
        lower = name.lower()
        if lower.endswith("vbaproject.bin"):
            add("macros", "high", "VBA project is preserved but not normalized.", name)
        if lower.startswith("_xmlsignatures/") or "origin.sigs" in lower:
            add(
                "digital-signature",
                "high",
                "Package signature will no longer validate after any content normalization.",
                name,
            )
        if "/activex/" in lower or lower.startswith("activex/"):
            add("activex", "high", "ActiveX content is suite-dependent.", name)
        if "/embeddings/" in lower:
            add("embedded-object", "high", "Embedded OLE/package object may render differently.", name)
        if "/externallinks/" in lower:
            add("external-link", "high", "External workbook/document link is environment-dependent.", name)
        if lower.endswith(".vml"):
            add("vml", "medium", "VML is legacy/transitional markup with renderer differences.", name)
        if "/diagrams/" in lower:
            add("diagram", "medium", "SmartArt/diagram rendering can differ between suites.", name)
        if "/charts/" in lower:
            add("chart", "medium", "Chart layout/rendering can differ between suites.", name)

    for name, data in xml_by_name.items():
        if b"<w:altChunk" in data or b":altChunk" in data:
            add("altchunk", "high", "altChunk requires an application import step and is not portable.", name)
        if b"AlternateContent" in data:
            add("alternate-content", "medium", "Markup Compatibility AlternateContent is preserved verbatim.", name)
        if b"<m:oMath" in data or b":oMath" in data:
            add("math", "medium", "Office Math rendering can differ between suites.", name)
        if b"<w:sdt" in data or b":sdt" in data:
            add("content-control", "medium", "Content controls are preserved but may behave differently.", name)

    return risks



def _lname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attr_local(element: ET.Element, local: str) -> str | None:
    for key, value in element.attrib.items():
        if key.rsplit("}", 1)[-1] == local:
            return value
    return None


def _docx_diagnostics(xml_by_name: dict[str, bytes]) -> tuple[dict[str, object], list[Risk]]:
    diagnostics: dict[str, object] = {}
    risks: list[Risk] = []
    document = xml_by_name.get("word/document.xml", b"")
    diagnostics["table_count"] = len(re.findall(rb"<w:tbl(?:\s|>)", document))
    diagnostics["tables_with_implicit_layout"] = len(
        re.findall(rb"<w:tblPr\b(?!.*?<w:tblLayout).*?</w:tblPr>", document, re.S)
    )
    theme_font_refs = 0
    theme_color_refs = 0
    for data in xml_by_name.values():
        theme_font_refs += len(re.findall(rb"\bw:(?:asciiTheme|hAnsiTheme|eastAsiaTheme|cstheme)\s*=", data))
        theme_color_refs += len(re.findall(rb"\bw:(?:themeColor|themeFill)\s*=", data))
    diagnostics["theme_font_references"] = theme_font_refs
    diagnostics["theme_color_references"] = theme_color_refs

    styles = xml_by_name.get("word/styles.xml")
    if styles:
        try:
            root = ET.fromstring(styles)
            parents: dict[str, str] = {}
            style_ids: set[str] = set()
            for style in root.iter():
                if _lname(style.tag) != "style":
                    continue
                sid = _attr_local(style, "styleId")
                if not sid:
                    continue
                style_ids.add(sid)
                for child in list(style):
                    if _lname(child.tag) == "basedOn":
                        parent = _attr_local(child, "val")
                        if parent:
                            parents[sid] = parent
            missing = sorted({p for p in parents.values() if p not in style_ids})
            cycles: list[list[str]] = []
            seen_cycles: set[tuple[str, ...]] = set()
            for start in style_ids:
                chain: list[str] = []
                index: dict[str, int] = {}
                current = start
                while current in parents:
                    if current in index:
                        cycle = chain[index[current]:] + [current]
                        canonical = tuple(sorted(set(cycle)))
                        if canonical not in seen_cycles:
                            seen_cycles.add(canonical)
                            cycles.append(cycle)
                        break
                    index[current] = len(chain)
                    chain.append(current)
                    current = parents[current]
            diagnostics["style_count"] = len(style_ids)
            diagnostics["style_based_on_count"] = len(parents)
            diagnostics["missing_style_parents"] = missing
            diagnostics["style_inheritance_cycles"] = cycles
            if missing:
                risks.append(Risk("missing-style-parent", "medium", "Styles reference missing basedOn parents.", "word/styles.xml"))
            if cycles:
                risks.append(Risk("style-inheritance-cycle", "high", "Style inheritance contains one or more cycles.", "word/styles.xml"))
        except ET.ParseError:
            risks.append(Risk("styles-parse", "high", "word/styles.xml could not be parsed for inheritance checks.", "word/styles.xml"))
    return diagnostics, risks


def _xlsx_diagnostics(xml_by_name: dict[str, bytes]) -> tuple[dict[str, object], list[Risk]]:
    diagnostics: dict[str, object] = {}
    risks: list[Risk] = []
    styles = xml_by_name.get("xl/styles.xml")
    custom_ids: set[int] = set()
    duplicate_ids: set[int] = set()
    xf_missing: set[int] = set()
    if styles:
        try:
            root = ET.fromstring(styles)
            seen: set[int] = set()
            for element in root.iter():
                local = _lname(element.tag)
                if local == "numFmt":
                    raw = element.attrib.get("numFmtId")
                    if raw and raw.isdigit():
                        value = int(raw)
                        if value in seen:
                            duplicate_ids.add(value)
                        seen.add(value)
                        custom_ids.add(value)
            builtin_max = 163
            for element in root.iter():
                if _lname(element.tag) == "xf":
                    raw = element.attrib.get("numFmtId")
                    if raw and raw.isdigit():
                        value = int(raw)
                        if value > builtin_max and value not in custom_ids:
                            xf_missing.add(value)
        except ET.ParseError:
            risks.append(Risk("xlsx-styles-parse", "high", "xl/styles.xml could not be parsed.", "xl/styles.xml"))
    diagnostics["custom_number_format_count"] = len(custom_ids)
    diagnostics["duplicate_custom_number_format_ids"] = sorted(duplicate_ids)
    diagnostics["missing_custom_number_format_references"] = sorted(xf_missing)
    if duplicate_ids:
        risks.append(Risk("duplicate-numfmt-id", "high", "Duplicate custom number-format IDs can be interpreted inconsistently.", "xl/styles.xml"))
    if xf_missing:
        risks.append(Risk("missing-numfmt", "high", "Cell styles reference custom number-format IDs that are not declared.", "xl/styles.xml"))

    priorities: list[int] = []
    cf_rules = 0
    for name, data in xml_by_name.items():
        if not name.startswith("xl/worksheets/"):
            continue
        cf_rules += len(re.findall(rb"<(?:\w+:)?cfRule\b", data))
        priorities.extend(int(v) for v in re.findall(rb"\bpriority=[\"'](\d+)[\"']", data))
    duplicates = sorted({p for p in priorities if priorities.count(p) > 1})
    diagnostics["conditional_format_rule_count"] = cf_rules
    diagnostics["duplicate_conditional_format_priorities"] = duplicates
    if duplicates:
        risks.append(Risk("conditional-format-priority", "medium", "Conditional-format rules contain duplicate priorities; ordering may differ between suites."))

    anchors = 0
    implicit_edit_as = 0
    for name, data in xml_by_name.items():
        if name.startswith("xl/drawings/"):
            anchors += len(re.findall(rb"<xdr:(?:twoCellAnchor|oneCellAnchor|absoluteAnchor)\b", data))
            implicit_edit_as += len(re.findall(rb"<xdr:twoCellAnchor\b(?![^>]*\beditAs\s*=)[^>]*>", data))
    diagnostics["drawing_anchor_count"] = anchors
    diagnostics["two_cell_anchors_with_implicit_edit_as"] = implicit_edit_as
    return diagnostics, risks


def _pptx_diagnostics(names: set[str], xml_by_name: dict[str, bytes]) -> tuple[dict[str, object], list[Risk]]:
    diagnostics: dict[str, object] = {
        "slide_count": len([n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]),
        "slide_master_count": len([n for n in names if re.fullmatch(r"ppt/slideMasters/slideMaster\d+\.xml", n)]),
        "slide_layout_count": len([n for n in names if re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", n)]),
    }
    risks: list[Risk] = []
    placeholder_fonts = 0
    scheme_colors = 0
    implicit_autofit = 0
    for name, data in xml_by_name.items():
        if not name.startswith("ppt/"):
            continue
        placeholder_fonts += len(re.findall(rb"\btypeface=[\"']\+(?:mj|mn)-(?:lt|ea|cs)[\"']", data))
        scheme_colors += len(re.findall(rb"<a:schemeClr\b", data))
        for body in re.findall(rb"<a:bodyPr\b[^>]*>(.*?)</a:bodyPr>", data, re.S):
            if not any(token in body for token in (b"<a:noAutofit", b"<a:normAutofit", b"<a:spAutoFit")):
                implicit_autofit += 1
    diagnostics["theme_font_placeholders"] = placeholder_fonts
    diagnostics["scheme_color_references"] = scheme_colors
    diagnostics["text_bodies_with_implicit_autofit"] = implicit_autofit
    if implicit_autofit:
        risks.append(Risk("pptx-autofit-implicit", "medium", "Some PowerPoint text bodies rely on implicit autofit behavior, which may differ between renderers."))
    return diagnostics, risks


def _format_diagnostics(kind: DocumentKind, names: set[str], xml_by_name: dict[str, bytes]) -> tuple[dict[str, object], list[Risk]]:
    if kind is DocumentKind.DOCX:
        return _docx_diagnostics(xml_by_name)
    if kind is DocumentKind.XLSX:
        return _xlsx_diagnostics(xml_by_name)
    return _pptx_diagnostics(names, xml_by_name)


def analyze_ooxml(path: str | Path) -> PackageAnalysis:
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(src)

    try:
        with ZipFile(src, "r") as zf:
            names = set(zf.namelist())
            kind = detect_document_kind(names)
            xml_by_name: dict[str, bytes] = {}
            xml_parts: list[bytes] = []
            fonts: set[str] = set()
            symbols = {symbol: 0 for symbol in SEMANTIC_COLOR_SYMBOLS}
            producer: str | None = None

            for info in zf.infolist():
                name = info.filename
                if not name.endswith((".xml", ".rels")):
                    continue
                data = zf.read(name)
                if name.endswith(".xml"):
                    xml_by_name[name] = data
                    xml_parts.append(data)
                    fonts.update(_extract_fonts(kind, name, data))
                    text = _decode_xml(data)
                    for symbol in symbols:
                        symbols[symbol] += text.count(symbol)
                if name == "docProps/app.xml":
                    producer = _extract_application(data)

            style_parts = tuple(
                sorted(
                    n for n in names
                    if n in {
                        "word/styles.xml",
                        "word/numbering.xml",
                        "xl/styles.xml",
                    }
                    or n.startswith("ppt/slideMasters/")
                    or n.startswith("ppt/slideLayouts/")
                )
            )
            has_theme = any("/theme/" in n and n.endswith(".xml") for n in names)
            base_risks = _risk_scan(names, xml_by_name)
            diagnostics, diagnostic_risks = _format_diagnostics(kind, names, xml_by_name)
            risks = tuple(base_risks + diagnostic_risks)

            return PackageAnalysis(
                path=str(src),
                document_kind=kind.value,
                producer=producer,
                conformance=_detect_conformance(xml_parts),
                entry_count=len(names),
                xml_part_count=sum(1 for n in names if n.endswith(".xml")),
                relationship_part_count=sum(1 for n in names if n.endswith(".rels")),
                required_fonts=tuple(sorted(fonts, key=str.casefold)),
                semantic_color_symbols={k: v for k, v in symbols.items() if v},
                has_theme=has_theme,
                style_parts=style_parts,
                risks=risks,
                diagnostics=diagnostics,
            )
    except BadZipFile as exc:
        raise ValueError(f"Input is not a valid OOXML ZIP package: {src}") from exc
