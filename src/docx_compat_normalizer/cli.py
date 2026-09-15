from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .normalizer import DEFAULT_LIBERATION_FONT_MAP, NormalizationOptions, normalize_ooxml


def _parse_font_map(values: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError(f"Invalid --font-map value {value!r}; expected OLD=NEW")
        old, new = value.split("=", 1)
        old, new = old.strip(), new.strip()
        if not old or not new:
            raise argparse.ArgumentTypeError(f"Invalid --font-map value {value!r}; expected OLD=NEW")
        mapping[old] = new
    return mapping


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ooxml-compat-normalize",
        description=(
            "Conservatively normalize DOCX/XLSX/PPTX packages for cross-suite compatibility "
            "without round-tripping through an office editor."
        ),
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--font-profile",
        choices=("preserve", "liberation"),
        default="preserve",
        help=(
            "preserve: do not rename fonts (default); liberation: map tested Microsoft core fonts "
            "to Liberation metric-compatible fonts"
        ),
    )
    parser.add_argument(
        "--font-map",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="Additional or overriding exact font mapping; may be repeated",
    )
    parser.add_argument(
        "--no-color-circles",
        action="store_true",
        help="Disable DOCX red/yellow/orange/green emoji-circle normalization",
    )
    parser.add_argument("--report", type=Path, help="Write the JSON normalization report to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        custom_map = _parse_font_map(args.font_map)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    font_map: dict[str, str] = {}
    if args.font_profile == "liberation":
        font_map.update(DEFAULT_LIBERATION_FONT_MAP)
    font_map.update(custom_map)

    try:
        report = normalize_ooxml(
            args.input,
            args.output,
            options=NormalizationOptions(
                fix_docx_color_circles=not args.no_color_circles,
                font_map=font_map,
            ),
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0
