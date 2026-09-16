from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .package import DocumentKind
from .theme import ThemeInfo, merge_themes, parse_theme_xml


@dataclass(frozen=True)
class ThemeResolver:
    default: ThemeInfo | None
    by_part: dict[str, ThemeInfo]
    warnings: tuple[str, ...]

    def for_part(self, part: str) -> ThemeInfo | None:
        return self.by_part.get(part, self.default)


def _rels_name(part: str) -> str:
    directory, basename = posixpath.split(part)
    return posixpath.join(directory, "_rels", basename + ".rels")


def _resolve_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def _relationships_for(zf: ZipFile, source_part: str) -> list[tuple[str, str]]:
    rel_name = _rels_name(source_part)
    if rel_name not in zf.namelist():
        return []
    try:
        root = ET.fromstring(zf.read(rel_name))
    except ET.ParseError:
        return []
    result: list[tuple[str, str]] = []
    for rel in list(root):
        rel_type = rel.attrib.get("Type", "")
        target = rel.attrib.get("Target", "")
        if not target or rel.attrib.get("TargetMode") == "External":
            continue
        result.append((rel_type, _resolve_target(source_part, target)))
    return result


def build_theme_resolver(zf: ZipFile, kind: DocumentKind) -> ThemeResolver:
    """Resolve themes conservatively, including PPTX slide/master inheritance.

    For PPTX, a slide normally inherits its theme through slideLayout -> slideMaster
    -> theme. That relationship chain is resolved per part. For parts without a unique
    chain, the resolver falls back to values that are identical across every theme in
    the package; conflicting values remain unresolved rather than using an arbitrary
    first theme.
    """
    names = set(zf.namelist())
    theme_parts = sorted(name for name in names if name.endswith(".xml") and "/theme/" in name)
    themes_by_part: dict[str, ThemeInfo] = {}
    warnings: list[str] = []
    for name in theme_parts:
        try:
            themes_by_part[name] = parse_theme_xml(zf.read(name))
        except Exception as exc:
            warnings.append(f"Theme part could not be parsed and was left untouched: {name}: {exc}")

    default = merge_themes(themes_by_part.values())
    by_part: dict[str, ThemeInfo] = {}

    if kind is DocumentKind.PPTX and themes_by_part:
        follow_types = (
            "/slideLayout",
            "/slideMaster",
            "/notesMaster",
            "/notesSlide",
            "/handoutMaster",
        )

        cache: dict[str, ThemeInfo | None] = {}

        def resolve(part: str, visiting: set[str] | None = None) -> ThemeInfo | None:
            if part in cache:
                return cache[part]
            visiting = set(visiting or ())
            if part in visiting:
                cache[part] = None
                return None
            visiting.add(part)
            relationships = _relationships_for(zf, part)
            direct = [target for rel_type, target in relationships if rel_type.endswith("/theme") and target in themes_by_part]
            if len(direct) == 1:
                cache[part] = themes_by_part[direct[0]]
                return cache[part]
            if len(direct) > 1:
                warnings.append(f"Multiple direct theme relationships found for {part}; leaving theme-dependent values unresolved")
                cache[part] = None
                return None
            inherited: list[ThemeInfo] = []
            for rel_type, target in relationships:
                if any(rel_type.endswith(suffix) for suffix in follow_types) and target in names:
                    candidate = resolve(target, visiting)
                    if candidate is not None:
                        inherited.append(candidate)
            unique = []
            for candidate in inherited:
                if candidate not in unique:
                    unique.append(candidate)
            if len(unique) == 1:
                cache[part] = unique[0]
                return unique[0]
            if len(unique) > 1:
                warnings.append(f"Conflicting inherited themes found for {part}; leaving values unresolved")
            cache[part] = None
            return None

        for part in sorted(n for n in names if n.startswith("ppt/") and n.endswith(".xml") and "/theme/" not in n):
            resolved = resolve(part)
            if resolved is not None:
                by_part[part] = resolved

    if len(themes_by_part) > 1:
        warnings.append(
            "Multiple theme parts detected; unresolved parts use only values identical across all themes"
        )

    return ThemeResolver(default=default, by_part=by_part, warnings=tuple(warnings))


def load_compatible_theme(zf: ZipFile) -> tuple[ThemeInfo | None, list[str]]:
    """Backward-compatible package-wide theme helper."""
    # The old helper did not know the package family. Merging remains a safe fallback.
    theme_parts = sorted(name for name in zf.namelist() if name.endswith(".xml") and "/theme/" in name)
    parsed: list[ThemeInfo] = []
    warnings: list[str] = []
    for name in theme_parts:
        try:
            parsed.append(parse_theme_xml(zf.read(name)))
        except Exception as exc:
            warnings.append(f"Theme part could not be parsed and was left untouched: {name}: {exc}")
    if len(parsed) > 1:
        warnings.append("Multiple theme parts detected; only common values are eligible for package-wide materialization")
    return merge_themes(parsed), warnings

def _get_attr(tag: bytes, local_name: bytes) -> bytes | None:
    pattern = re.compile(rb'\b(?:\w+:)?' + local_name + rb'\s*=\s*(["\'])(.*?)\1')
    match = pattern.search(tag)
    return match.group(2) if match else None


def _remove_attr(tag: bytes, local_name: bytes) -> bytes:
    return re.sub(
        rb'\s+\b(?:\w+:)?' + local_name + rb'\s*=\s*(["\']).*?\1',
        b'',
        tag,
        count=1,
    )


def _set_prefixed_attr(tag: bytes, prefix: bytes, local_name: bytes, value: str) -> bytes:
    pattern = re.compile(
        rb'(\b' + re.escape(prefix) + re.escape(local_name) + rb'\s*=\s*)(["\'])(.*?)\2'
    )
    encoded = value.encode("utf-8")
    if pattern.search(tag):
        return pattern.sub(lambda m: m.group(1) + m.group(2) + encoded + m.group(2), tag, count=1)
    insertion = b' ' + prefix + local_name + b'="' + encoded + b'"'
    if tag.endswith(b'/>'):
        return tag[:-2] + insertion + b'/>'
    return tag[:-1] + insertion + b'>'


def materialize_docx_theme_fonts(data: bytes, theme: ThemeInfo) -> tuple[bytes, int]:
    tag_re = re.compile(rb'<w:rFonts\b[^>]*>')
    count = 0

    attr_pairs = (
        (b'asciiTheme', b'ascii'),
        (b'hAnsiTheme', b'hAnsi'),
        (b'eastAsiaTheme', b'eastAsia'),
        (b'cstheme', b'cs'),
    )

    def patch(match: re.Match[bytes]) -> bytes:
        nonlocal count
        tag = match.group(0)
        for theme_attr, explicit_attr in attr_pairs:
            raw = _get_attr(tag, theme_attr)
            if not raw:
                continue
            resolved = theme.fonts.get(raw.decode("utf-8", errors="replace"))
            if not resolved:
                continue
            tag = _set_prefixed_attr(tag, b'w:', explicit_attr, resolved)
            tag = _remove_attr(tag, theme_attr)
            count += 1
        return tag

    return tag_re.sub(patch, data), count


def materialize_drawingml_theme_fonts(data: bytes, theme: ThemeInfo) -> tuple[bytes, int]:
    count = 0
    out = data
    for placeholder in ("+mj-lt", "+mn-lt", "+mj-ea", "+mn-ea", "+mj-cs", "+mn-cs"):
        resolved = theme.fonts.get(placeholder)
        if not resolved:
            continue
        pattern = re.compile(rb'(\btypeface\s*=\s*)(["\'])' + re.escape(placeholder.encode()) + rb'\2')
        out, n = pattern.subn(
            lambda m: m.group(1) + m.group(2) + resolved.encode("utf-8") + m.group(2),
            out,
        )
        count += n
    return out, count


def materialize_xlsx_theme_fonts(data: bytes, theme: ThemeInfo) -> tuple[bytes, int]:
    """Materialize SpreadsheetML major/minor scheme fonts in xl/styles.xml.

    A <font> using <scheme val="minor"/> is made explicit by setting its <name>
    to the resolved theme latin font and removing the scheme element. Existing font
    properties (size, family, charset, bold, etc.) remain byte-for-byte unchanged.
    """
    font_re = re.compile(rb'<font\b[^>]*>.*?</font>', re.S)
    count = 0

    def patch(match: re.Match[bytes]) -> bytes:
        nonlocal count
        block = match.group(0)
        scheme = re.search(rb'<scheme\b[^>]*\bval\s*=\s*(["\'])(major|minor)\1[^>]*/>', block)
        if not scheme:
            return block
        key = "+mj-lt" if scheme.group(2) == b"major" else "+mn-lt"
        resolved = theme.fonts.get(key)
        if not resolved:
            return block
        # Remove the theme scheme first, then materialize the resolved name. Doing
        # this before insertion avoids invalidating regex offsets.
        block = block[:scheme.start()] + block[scheme.end():]
        name_re = re.compile(rb'<name\b[^>]*\bval\s*=\s*(["\'])(.*?)\1[^>]*/>')
        if name_re.search(block):
            block = name_re.sub(
                lambda m: re.sub(
                    rb'(\bval\s*=\s*)(["\']).*?\2',
                    lambda x: x.group(1) + x.group(2) + resolved.encode() + x.group(2),
                    m.group(0),
                    count=1,
                ),
                block,
                count=1,
            )
        else:
            insertion = f'<name val="{resolved}"/>'.encode("utf-8")
            block = block.replace(b">", b">" + insertion, 1)
        count += 1
        return block

    return font_re.sub(patch, data), count


def _resolve_word_theme_color(theme: ThemeInfo, value: bytes) -> str | None:
    return theme.resolve_color(value.decode("ascii", errors="ignore"))


def materialize_docx_theme_colors(data: bytes, theme: ThemeInfo) -> tuple[bytes, int]:
    """Resolve Word theme colors only when no tint/shade transform is present."""
    tag_re = re.compile(rb'<w:[A-Za-z0-9]+\b[^>]*>')
    count = 0

    def patch(match: re.Match[bytes]) -> bytes:
        nonlocal count
        tag = match.group(0)
        # Text/border theme color -> explicit w:color.
        theme_color = _get_attr(tag, b'themeColor')
        if theme_color and not _get_attr(tag, b'themeTint') and not _get_attr(tag, b'themeShade'):
            resolved = _resolve_word_theme_color(theme, theme_color)
            if resolved:
                # <w:color> stores its direct value in w:val; borders and similar
                # properties store the fallback/direct value in w:color.
                direct_attr = b'val' if tag.startswith(b'<w:color') else b'color'
                tag = _set_prefixed_attr(tag, b'w:', direct_attr, resolved)
                tag = _remove_attr(tag, b'themeColor')
                count += 1
        # Shading theme fill -> explicit w:fill.
        theme_fill = _get_attr(tag, b'themeFill')
        if theme_fill and not _get_attr(tag, b'themeFillTint') and not _get_attr(tag, b'themeFillShade'):
            resolved = _resolve_word_theme_color(theme, theme_fill)
            if resolved:
                tag = _set_prefixed_attr(tag, b'w:', b'fill', resolved)
                tag = _remove_attr(tag, b'themeFill')
                count += 1
        return tag

    return tag_re.sub(patch, data), count


def materialize_drawingml_theme_colors(data: bytes, theme: ThemeInfo) -> tuple[bytes, int]:
    """Resolve empty DrawingML schemeClr elements to explicit sRGB.

    Elements carrying tint/shade/luminance/alpha transforms are intentionally left
    untouched because folding the full DrawingML color transform pipeline requires a
    more complete color engine.
    """
    count = 0
    out = data
    for name, rgb in theme.colors.items():
        name_b = re.escape(name.encode("ascii"))
        patterns = [
            re.compile(rb'<a:schemeClr\s+val=(["\'])' + name_b + rb'\1\s*/>'),
            re.compile(rb'<a:schemeClr\s+val=(["\'])' + name_b + rb'\1\s*>\s*</a:schemeClr>'),
        ]
        for pattern in patterns:
            out, n = pattern.subn(f'<a:srgbClr val="{rgb}"/>'.encode("ascii"), out)
            count += n
    return out, count


def materialize_xlsx_theme_colors(data: bytes, theme: ThemeInfo) -> tuple[bytes, int]:
    """Resolve SpreadsheetML theme colors when tint is absent or exactly zero."""
    tag_re = re.compile(rb'<(?:\w+:)?(?:color|fgColor|bgColor|tabColor)\b[^>]*>')
    count = 0

    def patch(match: re.Match[bytes]) -> bytes:
        nonlocal count
        tag = match.group(0)
        raw_theme = _get_attr(tag, b'theme')
        if raw_theme is None:
            return tag
        tint = _get_attr(tag, b'tint')
        if tint not in (None, b"0", b"0.0", b"0.000000"):
            return tag
        try:
            index = int(raw_theme)
        except ValueError:
            return tag
        rgb = theme.resolve_spreadsheet_color(index)
        if not rgb:
            return tag
        tag = _remove_attr(tag, b'theme')
        if tint is not None:
            tag = _remove_attr(tag, b'tint')
        # SpreadsheetML colors use ARGB.
        if re.search(rb'\brgb\s*=', tag):
            tag = re.sub(
                rb'(\brgb\s*=\s*)(["\']).*?\2',
                lambda m: m.group(1) + m.group(2) + b"FF" + rgb.encode() + m.group(2),
                tag,
                count=1,
            )
        else:
            insertion = b' rgb="FF' + rgb.encode() + b'"'
            tag = tag[:-2] + insertion + b'/>' if tag.endswith(b'/>') else tag[:-1] + insertion + b'>'
        count += 1
        return tag

    return tag_re.sub(patch, data), count


def materialize_docx_table_layout_default(data: bytes) -> tuple[bytes, int]:
    """Make Word's implicit table-layout default explicit.

    OOXML defaults an omitted tblLayout to autofit. Materializing that default does not
    force fixed widths; it simply removes one source of renderer-default ambiguity.
    """
    tblpr_re = re.compile(rb'<w:tblPr\b[^>]*>.*?</w:tblPr>', re.S)
    count = 0

    def patch(match: re.Match[bytes]) -> bytes:
        nonlocal count
        block = match.group(0)
        if b'<w:tblLayout' in block:
            return block
        count += 1
        return block[:-len(b'</w:tblPr>')] + b'<w:tblLayout w:type="autofit"/></w:tblPr>'

    return tblpr_re.sub(patch, data), count


def materialize_xlsx_anchor_default(data: bytes) -> tuple[bytes, int]:
    """Make DrawingML twoCellAnchor's default editAs mode explicit."""
    pattern = re.compile(rb'<xdr:twoCellAnchor\b(?![^>]*\beditAs\s*=)([^>]*)>')
    return pattern.subn(lambda m: b'<xdr:twoCellAnchor' + m.group(1) + b' editAs="twoCell">', data)


def apply_portability_rules(
    data: bytes,
    *,
    kind: DocumentKind,
    part: str,
    theme: ThemeInfo | None,
    materialize_theme_fonts: bool,
    materialize_theme_colors: bool,
    materialize_safe_defaults: bool,
) -> tuple[bytes, dict[str, int]]:
    """Apply rules whose semantics are explicit enough to be cross-suite candidates."""
    out = data
    counts: dict[str, int] = defaultdict(int)
    is_theme_part = "/theme/" in part

    if theme is not None and not is_theme_part and materialize_theme_fonts:
        if kind is DocumentKind.DOCX and part.startswith("word/"):
            out, n = materialize_docx_theme_fonts(out, theme)
            counts["docx_theme_fonts"] += n
        if kind is DocumentKind.XLSX and part == "xl/styles.xml":
            out, n = materialize_xlsx_theme_fonts(out, theme)
            counts["xlsx_theme_fonts"] += n
        # DrawingML is used by PPTX and by drawing/chart parts in DOCX/XLSX.
        out, n = materialize_drawingml_theme_fonts(out, theme)
        counts["drawingml_theme_fonts"] += n

    if theme is not None and not is_theme_part and materialize_theme_colors:
        if kind is DocumentKind.DOCX and part.startswith("word/"):
            out, n = materialize_docx_theme_colors(out, theme)
            counts["docx_theme_colors"] += n
        if kind is DocumentKind.XLSX and part.startswith("xl/"):
            out, n = materialize_xlsx_theme_colors(out, theme)
            counts["xlsx_theme_colors"] += n
        out, n = materialize_drawingml_theme_colors(out, theme)
        counts["drawingml_theme_colors"] += n

    if materialize_safe_defaults:
        if kind is DocumentKind.DOCX and part.startswith("word/") and part != "word/styles.xml":
            out, n = materialize_docx_table_layout_default(out)
            counts["docx_table_layout_defaults"] += n
        if kind is DocumentKind.XLSX and part.startswith("xl/drawings/"):
            out, n = materialize_xlsx_anchor_default(out)
            counts["xlsx_anchor_defaults"] += n

    return out, {key: value for key, value in counts.items() if value}
