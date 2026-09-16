from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from .analysis import analyze_ooxml
from .normalizer import (
    DEFAULT_LIBERATION_FONT_MAP,
    NormalizationError,
    NormalizationOptions,
    normalize_ooxml,
)
from .profile import FontPolicy, PROFILE_BY_NAME, INTEROP_TRANSITIONAL_V1, LossPolicy
from .sdk_validator import SdkValidationError, validate_with_openxml_sdk


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


def _load_font_inventory(path: Path | None) -> frozenset[str] | None:
    if path is None:
        return None
    fonts: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            fonts.add(line)
    return frozenset(fonts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ooxml-compat-normalize",
        description=(
            "Analyze and conservatively normalize DOCX/XLSX/PPTX packages toward a "
            "cross-suite OOXML interoperability profile without editor round-trips."
        ),
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?", help="Output OOXML path; omit with --audit-only")
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Analyze the input and print the compatibility preflight without writing an output file",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILE_BY_NAME),
        default=INTEROP_TRANSITIONAL_V1.name,
        help=(
            "Output profile: preserve-v1 changes nothing except explicit user mappings; "
            "interop-transitional-v1 applies conservative interoperability rules; "
            "portable-explicit-v1 additionally materializes safe theme/default semantics"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail closed when the requested portability guarantee cannot be verified",
    )
    parser.add_argument(
        "--font-policy",
        choices=("preserve", "map", "require-available"),
        default="preserve",
        help=(
            "preserve font names and report them; map applies explicit mappings; "
            "require-available verifies all declared fonts against --font-inventory"
        ),
    )
    parser.add_argument(
        "--font-inventory",
        type=Path,
        help="UTF-8 file containing one font family per line for the target renderer",
    )
    parser.add_argument(
        "--font-profile",
        choices=("preserve", "liberation"),
        default="preserve",
        help=(
            "Convenience mapping profile. liberation maps common Microsoft-compatible families "
            "to Liberation/Carlito/Caladea; it is never enabled implicitly."
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
        "--no-semantic-colors",
        action="store_true",
        help="Do not normalize supported Unicode color-semantic shapes to explicit OOXML colors",
    )
    parser.add_argument(
        "--no-color-circles",
        action="store_true",
        help=argparse.SUPPRESS,  # compatibility with v0.1
    )
    parser.add_argument(
        "--sdk-validation",
        choices=("auto", "off", "required"),
        default="auto",
        help=(
            "Open XML SDK validation: auto uses the bundled validator when available; "
            "off disables it; required fails if the validator is unavailable or cannot run"
        ),
    )
    parser.add_argument(
        "--sdk-max-errors",
        type=int,
        default=200,
        help="Maximum Open XML SDK validation errors retained in each report",
    )
    parser.add_argument("--report", type=Path, help="Write the JSON audit/normalization report to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        custom_map = _parse_font_map(args.font_map)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    try:
        inventory = _load_font_inventory(args.font_inventory)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.audit_only:
        try:
            report = {
                "preflight": analyze_ooxml(args.input).to_dict(),
                "openxml_sdk_validation": validate_with_openxml_sdk(
                    args.input, mode=args.sdk_validation, max_errors=args.sdk_max_errors
                ),
            }
        except (FileNotFoundError, SdkValidationError, ValueError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        print(rendered)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered + "\n", encoding="utf-8")
        return 0

    if args.output is None:
        parser.error("output is required unless --audit-only is used")

    font_map: dict[str, str] = {}
    if args.font_profile == "liberation":
        font_map.update(DEFAULT_LIBERATION_FONT_MAP)
    font_map.update(custom_map)

    policy = FontPolicy(args.font_policy)
    if font_map and policy is FontPolicy.PRESERVE:
        policy = FontPolicy.MAP
    if policy is FontPolicy.MAP and not font_map:
        parser.error("--font-policy map requires --font-profile liberation and/or --font-map OLD=NEW")
    if policy is FontPolicy.REQUIRE_AVAILABLE and inventory is None:
        parser.error("--font-policy require-available requires --font-inventory FILE")

    base_profile = PROFILE_BY_NAME[args.profile]
    profile = replace(
        base_profile,
        loss_policy=LossPolicy.STRICT if args.strict else base_profile.loss_policy,
        font_policy=policy,
        normalize_semantic_color_symbols=(
            False if (args.no_semantic_colors or args.no_color_circles)
            else base_profile.normalize_semantic_color_symbols
        ),
    )

    try:
        report = normalize_ooxml(
            args.input,
            args.output,
            options=NormalizationOptions(
                profile=profile,
                font_map=font_map,
                available_fonts=inventory,
                sdk_validation=args.sdk_validation,
                sdk_max_errors=args.sdk_max_errors,
            ),
        )
    except (FileNotFoundError, NormalizationError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0
