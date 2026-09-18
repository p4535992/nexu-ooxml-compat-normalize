"""Loss-averse OOXML interoperability normalizer."""

from .analysis import analyze_ooxml
from .normalizer import NormalizationOptions, normalize_ooxml
from .package import DocumentKind
from .profile import CanonicalProfile, FontPolicy, LossPolicy, INTEROP_TRANSITIONAL_V1, PORTABLE_EXPLICIT_V1, PRESERVE_V1

__all__ = [
    "CanonicalProfile",
    "DocumentKind",
    "FontPolicy",
    "LossPolicy",
    "NormalizationOptions",
    "INTEROP_TRANSITIONAL_V1",
    "PORTABLE_EXPLICIT_V1",
    "PRESERVE_V1",
    "analyze_ooxml",
    "normalize_ooxml",
]
__version__ = "0.4.0rc12"
