from __future__ import annotations

import unittest

from ooxml_compat_normalize.gui import (
    _build_missing_only_font_map,
    _filter_custom_map_to_missing,
    _parse_custom_font_map,
)


class FontGuiPolicyTests(unittest.TestCase):
    def test_custom_mapping_parser_accepts_semicolon_and_newline(self) -> None:
        parsed = _parse_custom_font_map(
            "Arial=Liberation Sans; Times New Roman=Liberation Serif\nCalibri=Carlito"
        )
        self.assertEqual(parsed["Arial"], "Liberation Sans")
        self.assertEqual(parsed["Times New Roman"], "Liberation Serif")
        self.assertEqual(parsed["Calibri"], "Carlito")

    def test_custom_mapping_parser_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValueError):
            _parse_custom_font_map("Arial")

    def test_missing_only_preserves_installed_font(self) -> None:
        mapping, unresolved = _build_missing_only_font_map(
            ["Arial", "Times New Roman"],
            frozenset({"Arial", "Liberation Serif"}),
            {
                "Arial": "Liberation Sans",
                "Times New Roman": "Liberation Serif",
            },
        )
        self.assertNotIn("Arial", mapping)
        self.assertEqual(mapping["Times New Roman"], "Liberation Serif")
        self.assertEqual(unresolved, [])

    def test_missing_only_does_not_map_to_unavailable_fallback(self) -> None:
        mapping, unresolved = _build_missing_only_font_map(
            ["Arial"],
            frozenset({"DejaVu Sans"}),
            {"Arial": "Liberation Sans"},
        )
        self.assertEqual(mapping, {})
        self.assertEqual(unresolved, ["Arial"])

    def test_custom_missing_only_requires_target_font_to_exist(self) -> None:
        mapping, unresolved = _filter_custom_map_to_missing(
            {"Example Font": "Fallback One", "Another": "Missing Target"},
            ["Example Font", "Another"],
            frozenset({"Fallback One"}),
        )
        self.assertEqual(mapping, {"Example Font": "Fallback One"})
        self.assertEqual(unresolved, ["Another → Missing Target"])


if __name__ == "__main__":
    unittest.main()
