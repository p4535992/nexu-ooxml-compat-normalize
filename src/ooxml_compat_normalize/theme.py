from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
from xml.etree import ElementTree as ET


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

# SpreadsheetML uses numeric indexes into the OOXML theme color scheme.
SPREADSHEET_THEME_INDEX = {
    0: "lt1",
    1: "dk1",
    2: "lt2",
    3: "dk2",
    4: "accent1",
    5: "accent2",
    6: "accent3",
    7: "accent4",
    8: "accent5",
    9: "accent6",
    10: "hlink",
    11: "folHlink",
}

# WordprocessingML uses long names for the four base theme colors.
WORD_THEME_COLOR_ALIASES = {
    "dark1": "dk1",
    "light1": "lt1",
    "dark2": "dk2",
    "light2": "lt2",
    "hyperlink": "hlink",
    "followedHyperlink": "folHlink",
}


@dataclass(frozen=True)
class ThemeInfo:
    colors: dict[str, str]
    fonts: dict[str, str]

    def resolve_color(self, name: str) -> str | None:
        key = WORD_THEME_COLOR_ALIASES.get(name, name)
        return self.colors.get(key)

    def resolve_spreadsheet_color(self, index: int) -> str | None:
        key = SPREADSHEET_THEME_INDEX.get(index)
        return self.colors.get(key) if key else None

    def resolve_placeholder(self, value: str) -> str | None:
        return self.fonts.get(value)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _color_value(node: ET.Element) -> str | None:
    for child in list(node):
        kind = _local(child.tag)
        if kind == "srgbClr":
            value = child.attrib.get("val")
            return value.upper() if value else None
        if kind == "sysClr":
            value = child.attrib.get("lastClr") or child.attrib.get("val")
            if value and re.fullmatch(r"[0-9A-Fa-f]{6}", value):
                return value.upper()
    return None


def parse_theme_xml(data: bytes) -> ThemeInfo:
    root = ET.fromstring(data)
    colors: dict[str, str] = {}
    fonts: dict[str, str] = {}

    clr_scheme = root.find(f".//{{{A_NS}}}clrScheme")
    if clr_scheme is not None:
        for child in list(clr_scheme):
            value = _color_value(child)
            if value:
                colors[_local(child.tag)] = value

    font_scheme = root.find(f".//{{{A_NS}}}fontScheme")
    if font_scheme is not None:
        for family, prefix in (("majorFont", "+mj"), ("minorFont", "+mn")):
            group = font_scheme.find(f"{{{A_NS}}}{family}")
            if group is None:
                continue
            for element_name, suffix in (("latin", "lt"), ("ea", "ea"), ("cs", "cs")):
                node = group.find(f"{{{A_NS}}}{element_name}")
                if node is not None:
                    typeface = (node.attrib.get("typeface") or "").strip()
                    if typeface:
                        fonts[f"{prefix}-{suffix}"] = typeface

    # Word's theme references use logical names rather than DrawingML +mj/+mn tokens.
    alias_map = {
        "majorAscii": "+mj-lt",
        "majorHAnsi": "+mj-lt",
        "majorEastAsia": "+mj-ea",
        "majorBidi": "+mj-cs",
        "minorAscii": "+mn-lt",
        "minorHAnsi": "+mn-lt",
        "minorEastAsia": "+mn-ea",
        "minorBidi": "+mn-cs",
    }
    for alias, placeholder in alias_map.items():
        if placeholder in fonts:
            fonts[alias] = fonts[placeholder]

    return ThemeInfo(colors=colors, fonts=fonts)


def merge_themes(themes: Iterable[ThemeInfo]) -> ThemeInfo | None:
    """Merge theme information only when every defined value agrees.

    Multiple PPTX masters can legally use different themes.  Applying the first theme
    package-wide would be unsafe, so conflicting values are deliberately omitted.
    """
    themes = list(themes)
    if not themes:
        return None
    color_keys = set().union(*(t.colors for t in themes))
    font_keys = set().union(*(t.fonts for t in themes))
    colors: dict[str, str] = {}
    fonts: dict[str, str] = {}
    for key in color_keys:
        values = {t.colors[key] for t in themes if key in t.colors}
        if len(values) == 1:
            colors[key] = next(iter(values))
    for key in font_keys:
        values = {t.fonts[key] for t in themes if key in t.fonts}
        if len(values) == 1:
            fonts[key] = next(iter(values))
    return ThemeInfo(colors=colors, fonts=fonts)
