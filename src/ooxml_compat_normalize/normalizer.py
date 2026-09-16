from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from zipfile import BadZipFile, ZipFile

from .analysis import SEMANTIC_COLOR_SYMBOLS, analyze_ooxml
from .package import DocumentKind, detect_document_kind
from .profile import CanonicalProfile, FontPolicy, INTEROP_TRANSITIONAL_V1, LossPolicy
from .rules import apply_portability_rules, build_theme_resolver
from .sdk_validator import SdkValidationError, validate_with_openxml_sdk


DEFAULT_LIBERATION_FONT_MAP: dict[str, str] = {
    "Times New Roman": "Liberation Serif",
    "Arial": "Liberation Sans",
    "Courier New": "Liberation Mono",
    "Calibri": "Carlito",
    "Cambria": "Caladea",
}


class NormalizationError(ValueError):
    """Raised when a requested compatibility guarantee cannot be satisfied."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _map_fonts_exactly(
    xml_bytes: bytes,
    font_map: Mapping[str, str],
    *,
    kind: DocumentKind,
    part: str,
) -> tuple[bytes, dict[str, int]]:
    """Patch only schema locations that actually declare font families.

    A global ``"Arial" -> "Liberation Sans"`` byte replacement is unsafe because
    user-visible text may itself contain a quoted font name.  This function limits
    changes to known OOXML font declaration attributes/elements while preserving the
    rest of the XML byte-for-byte.
    """
    out = xml_bytes
    counts: dict[str, int] = {}

    def replace_attr(data: bytes, attr_pattern: bytes, old: str, new: str) -> tuple[bytes, int]:
        old_b = re.escape(old.encode("utf-8"))
        pattern = re.compile(attr_pattern + rb'(?P<q>["\'])' + old_b + rb'(?P=q)')

        def repl(match: re.Match[bytes]) -> bytes:
            prefix = match.group(0)
            old_bytes = old.encode("utf-8")
            new_bytes = new.encode("utf-8")
            # Only the final exact attribute value is replaced; quote style/prefix stay intact.
            return prefix[:-len(old_bytes)-1] + new_bytes + prefix[-1:]

        return pattern.subn(repl, data)

    for old, new in font_map.items():
        total = 0

        # DrawingML: themes, PPTX runs, charts/shapes in all three OOXML families.
        out, n = replace_attr(out, rb'\btypeface\s*=\s*', old, new)
        total += n

        if kind is DocumentKind.DOCX and part.startswith("word/"):
            # WordprocessingML direct run-font declarations. Limit replacements to
            # <w:rFonts> so language attributes such as w:lang/@w:eastAsia are untouched.
            rfonts_tag = re.compile(rb'<(?:w:)?rFonts\b[^>]*>')

            def patch_rfonts(match: re.Match[bytes]) -> bytes:
                tag = match.group(0)
                for attr in (b'ascii', b'hAnsi', b'eastAsia', b'cs'):
                    tag, _ = replace_attr(tag, rb'\b(?:w:)?' + attr + rb'\s*=\s*', old, new)
                return tag

            before_rfonts = out
            out = rfonts_tag.sub(patch_rfonts, out)
            # Count exact old font values removed from rFonts tags only.
            def count_in_rfonts(data: bytes) -> int:
                count = 0
                for m in rfonts_tag.finditer(data):
                    tag = m.group(0)
                    for attr in (b'ascii', b'hAnsi', b'eastAsia', b'cs'):
                        pat = re.compile(rb'\b(?:w:)?' + attr + rb'\s*=\s*["\']' + re.escape(old.encode("utf-8")) + rb'["\']')
                        count += len(pat.findall(tag))
                return count
            total += count_in_rfonts(before_rfonts)

            # Font table declaration: <w:font w:name="Arial">.
            font_tag = re.compile(
                rb'(<(?:w:)?font\b[^>]*\b(?:w:)?name\s*=\s*)(?P<q>["\'])'
                + re.escape(old.encode("utf-8"))
                + rb'(?P=q)'
            )
            out, n = font_tag.subn(
                lambda m: m.group(1) + m.group("q") + new.encode("utf-8") + m.group("q"),
                out,
            )
            total += n

        if kind is DocumentKind.XLSX and part.startswith("xl/"):
            # SpreadsheetML rich text: <rFont val="...">.
            rfont_tag = re.compile(
                rb'(<(?:\w+:)?rFont\b[^>]*\bval\s*=\s*)(?P<q>["\'])'
                + re.escape(old.encode("utf-8"))
                + rb'(?P=q)'
            )
            out, n = rfont_tag.subn(
                lambda m: m.group(1) + m.group("q") + new.encode("utf-8") + m.group("q"),
                out,
            )
            total += n

            # Cell style fonts live in xl/styles.xml as <font><name val="..."/>...</font>.
            if part == "xl/styles.xml":
                name_tag = re.compile(
                    rb'(<(?:\w+:)?name\b[^>]*\bval\s*=\s*)(?P<q>["\'])'
                    + re.escape(old.encode("utf-8"))
                    + rb'(?P=q)'
                )
                out, n = name_tag.subn(
                    lambda m: m.group(1) + m.group("q") + new.encode("utf-8") + m.group("q"),
                    out,
                )
                total += n

        if total:
            counts[old] = total

    return out, counts


def _docx_symbol_rpr(color: str, font: str) -> bytes:
    return (
        b'<w:rPr>'
        + (
            f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" '
            f'w:eastAsia="{font}" w:cs="{font}"/>'
        ).encode("utf-8")
        + f'<w:color w:val="{color}"/>'.encode("ascii")
        + b'</w:rPr>'
    )


def _normalize_docx_semantic_color_symbols(document_xml: bytes) -> tuple[bytes, dict[str, int]]:
    """Convert simple color-semantic emoji runs to explicit OOXML formatting.

    The transformation is intentionally surgical. It only touches an isolated symbol
    in a run with no meaningful existing run properties. More complex runs are left
    untouched and are reported by post-analysis rather than silently rebuilt.
    """
    out = document_xml
    counts: dict[str, int] = {symbol: 0 for symbol in SEMANTIC_COLOR_SYMBOLS}

    for symbol, (_shape, replacement, color) in SEMANTIC_COLOR_SYMBOLS.items():
        symbol_b = symbol.encode("utf-8")
        replacement_b = replacement.encode("utf-8")
        rpr = _docx_symbol_rpr(color, "DejaVu Sans")
        patterns = [
            re.compile(
                rb'<w:r><w:rPr></w:rPr><w:t(?P<attrs>[^>]*)>'
                + re.escape(symbol_b)
                + rb'(?P<space> ?)</w:t></w:r>'
            ),
            re.compile(
                rb'<w:r><w:rPr\s*/><w:t(?P<attrs>[^>]*)>'
                + re.escape(symbol_b)
                + rb'(?P<space> ?)</w:t></w:r>'
            ),
            re.compile(
                rb'<w:r><w:t(?P<attrs>[^>]*)>'
                + re.escape(symbol_b)
                + rb'(?P<space> ?)</w:t></w:r>'
            ),
        ]

        for pattern in patterns:
            def repl(match: re.Match[bytes]) -> bytes:
                counts[symbol] += 1
                return (
                    b'<w:r>' + rpr + b'<w:t' + match.group("attrs") + b'>'
                    + replacement_b + match.group("space") + b'</w:t></w:r>'
                )

            out = pattern.sub(repl, out)

    return out, counts


def _pptx_symbol_rpr(color: str, font: str) -> bytes:
    return (
        b'<a:rPr>'
        b'<a:solidFill>'
        + f'<a:srgbClr val="{color}"/>'.encode("ascii")
        + b'</a:solidFill>'
        + f'<a:latin typeface="{font}"/>'.encode("utf-8")
        + b'</a:rPr>'
    )


def _normalize_pptx_semantic_color_symbols(xml_bytes: bytes) -> tuple[bytes, dict[str, int]]:
    """Normalize isolated symbols in simple DrawingML text runs."""
    out = xml_bytes
    counts = {symbol: 0 for symbol in SEMANTIC_COLOR_SYMBOLS}
    for symbol, (_shape, replacement, color) in SEMANTIC_COLOR_SYMBOLS.items():
        symbol_b = symbol.encode("utf-8")
        replacement_b = replacement.encode("utf-8")
        rpr = _pptx_symbol_rpr(color, "DejaVu Sans")
        patterns = [
            re.compile(rb'<a:r><a:rPr\s*/><a:t>' + re.escape(symbol_b) + rb'(?P<space> ?)</a:t></a:r>'),
            re.compile(rb'<a:r><a:t>' + re.escape(symbol_b) + rb'(?P<space> ?)</a:t></a:r>'),
        ]
        for pattern in patterns:
            def repl(match: re.Match[bytes]) -> bytes:
                counts[symbol] += 1
                return b'<a:r>' + rpr + b'<a:t>' + replacement_b + match.group("space") + b'</a:t></a:r>'
            out = pattern.sub(repl, out)
    return out, counts


def _xlsx_rpr(color: str, font: str) -> bytes:
    # SpreadsheetML ARGB is alpha + RGB.
    return (
        b'<rPr>'
        + f'<rFont val="{font}"/>'.encode("utf-8")
        + f'<color rgb="FF{color}"/>'.encode("ascii")
        + b'</rPr>'
    )


def _normalize_xlsx_semantic_color_symbols(xml_bytes: bytes) -> tuple[bytes, dict[str, int]]:
    """Normalize isolated symbols in existing SpreadsheetML rich-text runs.

    Plain shared strings are deliberately not rebuilt into rich text yet; doing so can
    affect phonetic properties and consumers. They remain detectable in post-analysis.
    """
    out = xml_bytes
    counts = {symbol: 0 for symbol in SEMANTIC_COLOR_SYMBOLS}
    for symbol, (_shape, replacement, color) in SEMANTIC_COLOR_SYMBOLS.items():
        symbol_b = symbol.encode("utf-8")
        replacement_b = replacement.encode("utf-8")
        rpr = _xlsx_rpr(color, "DejaVu Sans")
        patterns = [
            re.compile(rb'<r><rPr\s*/><t(?P<attrs>[^>]*)>' + re.escape(symbol_b) + rb'(?P<space> ?)</t></r>'),
            re.compile(rb'<r><t(?P<attrs>[^>]*)>' + re.escape(symbol_b) + rb'(?P<space> ?)</t></r>'),
        ]
        for pattern in patterns:
            def repl(match: re.Match[bytes]) -> bytes:
                counts[symbol] += 1
                return (
                    b'<r>' + rpr + b'<t' + match.group("attrs") + b'>'
                    + replacement_b + match.group("space") + b'</t></r>'
                )
            out = pattern.sub(repl, out)
    return out, counts


@dataclass(frozen=True)
class NormalizationOptions:
    profile: CanonicalProfile = INTEROP_TRANSITIONAL_V1
    font_map: Mapping[str, str] | None = None
    available_fonts: frozenset[str] | None = None
    normalize_semantic_color_symbols: bool | None = None
    # Backward-compatibility alias for the first prototype CLI/API.
    fix_docx_color_circles: bool | None = None
    sdk_validation: str = "auto"
    sdk_max_errors: int = 200


def _effective_symbol_policy(options: NormalizationOptions) -> bool:
    if options.normalize_semantic_color_symbols is not None:
        return options.normalize_semantic_color_symbols
    if options.fix_docx_color_circles is not None:
        return options.fix_docx_color_circles
    return options.profile.normalize_semantic_color_symbols


def _strict_preflight(
    analysis: dict,
    options: NormalizationOptions,
    font_map: Mapping[str, str],
) -> list[str]:
    errors: list[str] = []
    profile = options.profile
    if profile.conformance_target.value == "transitional" and analysis["conformance"] == "strict":
        errors.append("Strict OOXML -> Transitional conversion is not implemented safely yet")

    required_fonts = list(analysis["required_fonts"])
    if profile.loss_policy is LossPolicy.STRICT and required_fonts and options.available_fonts is None:
        errors.append(
            "Strict mode cannot verify font portability without an explicit target font inventory"
        )
    elif options.available_fonts is not None:
        available_folded = {font.casefold() for font in options.available_fonts}
        expected_fonts = [font_map.get(font, font) for font in required_fonts]
        missing = [font for font in expected_fonts if font.casefold() not in available_folded]
        if missing:
            errors.append("Target font inventory is missing: " + ", ".join(sorted(set(missing), key=str.casefold)))

    if profile.font_policy is FontPolicy.REQUIRE_AVAILABLE and options.available_fonts is None:
        errors.append("FontPolicy.REQUIRE_AVAILABLE needs an explicit target font inventory")

    high_risks = [r for r in analysis["risks"] if r["severity"] == "high"]
    if high_risks:
        errors.append(
            "High-risk suite-dependent features present: "
            + ", ".join(sorted({r["code"] for r in high_risks}))
        )
    return errors


def normalize_ooxml(
    src: str | Path,
    dst: str | Path,
    *,
    options: NormalizationOptions | None = None,
) -> dict:
    """Normalize a DOCX/XLSX/PPTX package without an editor round-trip.

    Preservation is the default.  The engine copies the OPC package entry-by-entry,
    applies only registered byte-local rules, then verifies package invariants and
    re-analyzes the output.  It never claims renderer equivalence; strict mode fails
    instead of silently accepting risks it cannot verify.
    """
    src_path = Path(src)
    dst_path = Path(dst)
    options = options or NormalizationOptions()
    profile = options.profile
    font_map = dict(options.font_map or {})
    normalize_symbols = _effective_symbol_policy(options)

    if not src_path.is_file():
        raise FileNotFoundError(src_path)
    if src_path.resolve() == dst_path.resolve():
        raise ValueError("Input and output must be different paths; in-place editing is intentionally disabled")

    pre = analyze_ooxml(src_path).to_dict()
    try:
        sdk_preflight = validate_with_openxml_sdk(
            src_path, mode=options.sdk_validation, max_errors=options.sdk_max_errors
        )
    except SdkValidationError as exc:
        raise NormalizationError(f"Open XML SDK pre-flight failed: {exc}") from exc
    strict_errors = _strict_preflight(pre, options, font_map)
    if profile.loss_policy is LossPolicy.STRICT and strict_errors:
        raise NormalizationError("Strict preflight failed: " + "; ".join(strict_errors))

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with ZipFile(src_path, "r") as zin:
            names = set(zin.namelist())
            kind = detect_document_kind(names)
            original_order = [info.filename for info in zin.infolist()]
            changed_parts: list[dict] = []
            font_counts: dict[str, int] = {}
            portability_rule_counts: dict[str, int] = {}
            symbol_counts = {symbol: 0 for symbol in SEMANTIC_COLOR_SYMBOLS}
            warnings: list[str] = list(strict_errors)
            theme_resolver = build_theme_resolver(zin, kind)
            warnings.extend(theme_resolver.warnings)
            if (profile.materialize_theme_fonts or profile.materialize_theme_colors) and theme_resolver.default is None and not theme_resolver.by_part:
                warnings.append("Theme materialization was requested but no usable package theme was found")

            with ZipFile(dst_path, "w") as zout:
                for info in zin.infolist():
                    original = zin.read(info.filename)
                    data = original

                    if normalize_symbols and info.filename.endswith(".xml"):
                        local_symbols: dict[str, int] | None = None
                        if kind is DocumentKind.DOCX and info.filename.startswith("word/"):
                            data, local_symbols = _normalize_docx_semantic_color_symbols(data)
                        elif kind is DocumentKind.PPTX and info.filename.startswith("ppt/"):
                            data, local_symbols = _normalize_pptx_semantic_color_symbols(data)
                        elif kind is DocumentKind.XLSX and info.filename.startswith("xl/"):
                            data, local_symbols = _normalize_xlsx_semantic_color_symbols(data)
                        if local_symbols:
                            for symbol, count in local_symbols.items():
                                symbol_counts[symbol] += count

                    if info.filename.endswith(".xml") and (
                        profile.materialize_theme_fonts
                        or profile.materialize_theme_colors
                        or profile.materialize_safe_defaults
                    ):
                        data, local_rules = apply_portability_rules(
                            data,
                            kind=kind,
                            part=info.filename,
                            theme=theme_resolver.for_part(info.filename),
                            materialize_theme_fonts=profile.materialize_theme_fonts,
                            materialize_theme_colors=profile.materialize_theme_colors,
                            materialize_safe_defaults=profile.materialize_safe_defaults,
                        )
                        for rule_name, count in local_rules.items():
                            portability_rule_counts[rule_name] = portability_rule_counts.get(rule_name, 0) + count

                    if font_map and info.filename.endswith(".xml"):
                        data, local_fonts = _map_fonts_exactly(data, font_map, kind=kind, part=info.filename)
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

                    zout.writestr(info, data)

        # Post-write package integrity and preservation checks.
        with ZipFile(src_path, "r") as check_in, ZipFile(dst_path, "r") as zout:
            corrupt = zout.testzip()
            output_order = [info.filename for info in zout.infolist()]
            output_names = set(output_order)
            if corrupt:
                raise NormalizationError(f"Output ZIP integrity failure in part: {corrupt}")
            if output_names != names:
                raise NormalizationError("Output package part set differs from input")
            if output_order != original_order:
                warnings.append("ZIP entry order changed")
            if profile.preserve_relationships:
                for name in names:
                    if name.endswith(".rels") and zout.read(name) != check_in.read(name):
                        raise NormalizationError(f"Relationship part changed unexpectedly: {name}")
            if profile.preserve_content_types and "[Content_Types].xml" in names:
                if zout.read("[Content_Types].xml") != check_in.read("[Content_Types].xml"):
                    raise NormalizationError("[Content_Types].xml changed unexpectedly")

    except BadZipFile as exc:
        raise ValueError(f"Input is not a valid OOXML ZIP package: {src_path}") from exc

    post = analyze_ooxml(dst_path).to_dict()
    try:
        sdk_postflight = validate_with_openxml_sdk(
            dst_path, mode=options.sdk_validation, max_errors=options.sdk_max_errors
        )
    except SdkValidationError as exc:
        raise NormalizationError(f"Open XML SDK post-flight failed: {exc}") from exc

    sdk_regression: str | None = None
    if sdk_postflight.get("available") and sdk_postflight.get("valid") is False:
        pre_valid = sdk_preflight.get("valid")
        pre_errors = sdk_preflight.get("errorCount")
        post_errors = sdk_postflight.get("errorCount")
        if pre_valid is True:
            sdk_regression = (
                f"Open XML SDK regression: input validated cleanly but output has {post_errors} error(s)"
            )
        elif isinstance(pre_errors, int) and isinstance(post_errors, int) and post_errors > pre_errors:
            sdk_regression = (
                f"Open XML SDK regression: validation errors increased from {pre_errors} to {post_errors}"
            )
        elif pre_valid is None:
            warnings.append(
                f"Open XML SDK post-flight reported {post_errors} validation error(s); pre-flight comparison unavailable"
            )

    if sdk_regression:
        warnings.append(sdk_regression)
        if profile.loss_policy is LossPolicy.STRICT:
            raise NormalizationError(sdk_regression)

    remaining_symbols = post["semantic_color_symbols"] if normalize_symbols else {}
    if remaining_symbols:
        warnings.append(
            "Some color-semantic Unicode symbols remain because they were inside complex runs "
            "that the current rules intentionally do not rebuild: "
            + ", ".join(f"{k}={v}" for k, v in remaining_symbols.items())
        )
        if profile.loss_policy is LossPolicy.STRICT:
            raise NormalizationError(warnings[-1])

    guarantee = "preservation-verified"
    if profile.loss_policy is LossPolicy.STRICT and not warnings:
        guarantee = "strict-preflight-and-preservation-verified"
    elif warnings:
        guarantee = "best-effort-with-warnings"

    return {
        "input": str(src_path),
        "output": str(dst_path),
        "document_kind": kind.value,
        "profile": profile.name,
        "guarantee_level": guarantee,
        "preflight": pre,
        "postflight": post,
        "openxml_sdk_validation": {
            "preflight": sdk_preflight,
            "postflight": sdk_postflight,
        },
        "semantic_color_symbol_replacements": {k: v for k, v in symbol_counts.items() if v},
        # Backward-compatible report key.
        "emoji_replacements": {k: v for k, v in symbol_counts.items() if v},
        "font_mapping": font_map,
        "font_attribute_replacements": font_counts,
        "portability_rule_applications": portability_rule_counts,
        "changed_part_count": len(changed_parts),
        "changed_parts": changed_parts,
        "warnings": warnings,
        "preservation_checks": {
            "same_part_set": True,
            "relationships_unchanged": profile.preserve_relationships,
            "content_types_unchanged": profile.preserve_content_types,
            "zip_integrity": "ok",
        },
    }
