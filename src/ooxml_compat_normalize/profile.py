from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConformanceTarget(str, Enum):
    """OOXML conformance target used by the interoperability profile."""

    PRESERVE = "preserve"
    TRANSITIONAL = "transitional"


class LossPolicy(str, Enum):
    """How the normalizer reacts when it cannot prove a safe transformation."""

    REPORT = "report"
    STRICT = "strict"


class FontPolicy(str, Enum):
    """Font handling policy.

    PRESERVE keeps document font declarations untouched and reports them.
    MAP applies an explicit caller-supplied mapping.
    REQUIRE_AVAILABLE preserves names but fails in strict mode when a supplied
    target inventory does not contain every declared font.
    """

    PRESERVE = "preserve"
    MAP = "map"
    REQUIRE_AVAILABLE = "require-available"


@dataclass(frozen=True)
class CanonicalProfile:
    """Contract for a cross-suite OOXML output.

    The conservative profile preserves theme indirections and implicit defaults.
    The portable-explicit profile materializes a subset of theme/default semantics
    only when the transformation is well-defined and byte-local.
    """

    name: str = "interop-transitional-v1"
    conformance_target: ConformanceTarget = ConformanceTarget.TRANSITIONAL
    loss_policy: LossPolicy = LossPolicy.REPORT
    font_policy: FontPolicy = FontPolicy.PRESERVE
    preserve_unknown_parts: bool = True
    preserve_relationships: bool = True
    preserve_content_types: bool = True
    preserve_styles: bool = True
    preserve_themes: bool = True
    preserve_layout: bool = True
    normalize_semantic_color_symbols: bool = True
    materialize_theme_fonts: bool = False
    materialize_theme_colors: bool = False
    materialize_safe_defaults: bool = False


PRESERVE_V1 = CanonicalProfile(
    name="preserve-v1",
    conformance_target=ConformanceTarget.PRESERVE,
    normalize_semantic_color_symbols=False,
)

INTEROP_TRANSITIONAL_V1 = CanonicalProfile()

PORTABLE_EXPLICIT_V1 = CanonicalProfile(
    name="portable-explicit-v1",
    materialize_theme_fonts=True,
    materialize_theme_colors=True,
    materialize_safe_defaults=True,
)

PROFILE_BY_NAME = {
    PRESERVE_V1.name: PRESERVE_V1,
    INTEROP_TRANSITIONAL_V1.name: INTEROP_TRANSITIONAL_V1,
    PORTABLE_EXPLICIT_V1.name: PORTABLE_EXPLICIT_V1,
}
