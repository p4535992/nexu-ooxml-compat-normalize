from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping
from zipfile import BadZipFile, ZipFile


class DocumentKind(str, Enum):
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"


DEFAULT_LIBERATION_FONT_MAP: dict[str, str] = {
    "Times New Roman": "Liberation Serif",
    "Arial": "Liberation Sans",
    "Courier New": "Liberation Mono",
}

COLOR_CIRCLES: dict[str, str] = {
    "🔴": "FF0000",
    "🟡": "FFC000",
    "🟠": "ED7D31",
    "🟢": "00B050",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_document_kind(names: set[str]) -> DocumentKind:
    if "word/document.xml" in names:
        return DocumentKind.DOCX
    if "xl/workbook.xml" in names:
        return DocumentKind.XLSX
    if "ppt/presentation.xml" in names:
        return DocumentKind.PPTX
    raise ValueError("Unsupported OOXML package: expected DOCX, XLSX, or PPTX")


def _map_fonts_exactly(xml_bytes: bytes, font_map: Mapping[str, str]) -> tuple[bytes, dict[str, int]]:
    """Replace exact quoted font attribute values only.

    This deliberately avoids substring replacement: mapping ``Arial`` must not alter
    ``Arial Unicode MS``. The operation is byte-local and does not parse/re-serialize XML.
    """
    out = xml_bytes
    counts: dict[str, int] = {}
    for old, new in font_map.items():
        needle = f'"{old}"'.encode("utf-8")
        replacement = f'"{new}"'.encode("utf-8")
        count = out.count(needle)
        if count:
            out = out.replace(needle, replacement)
            counts[old] = count
    return out, counts


def _docx_circle_rpr(color: str) -> bytes:
    return (
        b'<w:rPr>'
        b'<w:rFonts w:ascii="Liberation Sans" w:hAnsi="Liberation Sans" '
        b'w:eastAsia="Liberation Sans" w:cs="Liberation Sans"/>'
        + f'<w:color w:val="{color}"/>'.encode("ascii")
        + b'</w:rPr>'
    )


def _normalize_docx_color_circles(document_xml: bytes) -> tuple[bytes, dict[str, int]]:
    """Convert selected color emoji circles to a normal glyph plus explicit OOXML color.

    Only simple runs are touched. Runs with non-empty run properties are intentionally
    skipped so existing author formatting is not silently overwritten.
    """
    out = document_xml
    counts: dict[str, int] = {emoji: 0 for emoji in COLOR_CIRCLES}

    for emoji, color in COLOR_CIRCLES.items():
        emoji_b = emoji.encode("utf-8")
        rpr = _docx_circle_rpr(color)

        # Conservative LibreOffice patterns observed in real documents:
        #   <w:r><w:rPr></w:rPr><w:t ...>🔴 </w:t></w:r>
        #   <w:r><w:rPr/><w:t ...>🔴 </w:t></w:r>
        #   <w:r><w:t ...>🔴 </w:t></w:r>
        # Text attributes are preserved verbatim.
        patterns = [
            re.compile(
                rb'<w:r><w:rPr></w:rPr><w:t(?P<attrs>[^>]*)>'
                + re.escape(emoji_b)
                + rb'(?P<space> ?)</w:t></w:r>'
            ),
            re.compile(
                rb'<w:r><w:rPr\s*/><w:t(?P<attrs>[^>]*)>'
                + re.escape(emoji_b)
                + rb'(?P<space> ?)</w:t></w:r>'
            ),
            re.compile(
                rb'<w:r><w:t(?P<attrs>[^>]*)>'
                + re.escape(emoji_b)
                + rb'(?P<space> ?)</w:t></w:r>'
            ),
        ]

        for pattern in patterns:
            def repl(match: re.Match[bytes]) -> bytes:
                counts[emoji] += 1
                return (
                    b'<w:r>'
                    + rpr
                    + b'<w:t'
                    + match.group("attrs")
                    + b'>\xe2\xac\xa4'
                    + match.group("space")
                    + b'</w:t></w:r>'
                )

            out = pattern.sub(repl, out)

    return out, counts


@dataclass(frozen=True)
class NormalizationOptions:
    fix_docx_color_circles: bool = True
    font_map: Mapping[str, str] | None = None


def normalize_ooxml(
    src: str | Path,
    dst: str | Path,
    *,
    options: NormalizationOptions | None = None,
) -> dict:
    """Normalize a DOCX/XLSX/PPTX package without opening it in an office editor.

    The ZIP package is copied entry-by-entry. Only selected XML parts are patched and all
    unselected parts are copied unchanged.
    """
    src_path = Path(src)
    dst_path = Path(dst)
    options = options or NormalizationOptions()
    font_map = dict(options.font_map or {})

    if not src_path.is_file():
        raise FileNotFoundError(src_path)
    if src_path.resolve() == dst_path.resolve():
        raise ValueError("Input and output must be different paths; in-place editing is intentionally disabled")

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with ZipFile(src_path, "r") as zin:
            names = set(zin.namelist())
            kind = detect_document_kind(names)

            changed_parts: list[dict] = []
            font_counts: dict[str, int] = {}
            emoji_counts = {emoji: 0 for emoji in COLOR_CIRCLES}
            warnings: list[str] = []

            if kind is not DocumentKind.DOCX and options.fix_docx_color_circles:
                warnings.append(
                    "Color-circle normalization is currently implemented only for DOCX; "
                    f"{kind.value.upper()} content was not rewritten for emoji colors."
                )

            with ZipFile(dst_path, "w") as zout:
                for info in zin.infolist():
                    original = zin.read(info.filename)
                    data = original

                    if (
                        kind is DocumentKind.DOCX
                        and options.fix_docx_color_circles
                        and info.filename == "word/document.xml"
                    ):
                        data, local_emoji = _normalize_docx_color_circles(data)
                        for emoji, count in local_emoji.items():
                            emoji_counts[emoji] += count

                    if font_map and info.filename.endswith(".xml"):
                        data, local_fonts = _map_fonts_exactly(data, font_map)
                        for old, count in local_fonts.items():
                            font_counts[old] = font_counts.get(old, 0) + count

                    if data != original:
                        changed_parts.append(
                            {
                                "part": info.filename,
                                "before_sha256": _sha256(original),
                                "after_sha256": _sha256(data),
                                "before_bytes": len(original),
                                "after_bytes": len(data),
                            }
                        )

                    # Reuse the original ZipInfo to preserve entry metadata, order and
                    # compression method as far as Python's zipfile API permits.
                    zout.writestr(info, data)

    except BadZipFile as exc:
        raise ValueError(f"Input is not a valid OOXML ZIP package: {src_path}") from exc

    return {
        "input": str(src_path),
        "output": str(dst_path),
        "document_kind": kind.value,
        "fix_docx_color_circles": options.fix_docx_color_circles,
        "font_mapping": font_map,
        "emoji_replacements": emoji_counts,
        "font_attribute_replacements": font_counts,
        "changed_part_count": len(changed_parts),
        "changed_parts": changed_parts,
        "warnings": warnings,
    }
