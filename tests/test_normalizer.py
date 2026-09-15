from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from docx_compat_normalizer.normalizer import (
    DEFAULT_LIBERATION_FONT_MAP,
    DocumentKind,
    NormalizationOptions,
    detect_document_kind,
    normalize_ooxml,
)


def make_package(path: Path, entries: dict[str, bytes]) -> None:
    with ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


class DetectionTests(unittest.TestCase):
    def test_detects_docx(self) -> None:
        self.assertEqual(detect_document_kind({"word/document.xml"}), DocumentKind.DOCX)

    def test_detects_xlsx(self) -> None:
        self.assertEqual(detect_document_kind({"xl/workbook.xml"}), DocumentKind.XLSX)

    def test_detects_pptx(self) -> None:
        self.assertEqual(detect_document_kind({"ppt/presentation.xml"}), DocumentKind.PPTX)


class NormalizeTests(unittest.TestCase):
    def test_docx_circle_and_font_mapping_are_surgical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.docx"
            dst = td / "out.docx"
            document = (
                '<w:document xmlns:w="urn:test"><w:body>'
                '<w:r><w:rPr></w:rPr><w:t xml:space="preserve">🔴 </w:t></w:r>'
                '<w:r><w:rPr><w:rFonts w:ascii="Arial"/></w:rPr><w:t>Hello</w:t></w:r>'
                '</w:body></w:document>'
            ).encode("utf-8")
            untouched = b"unchanged-binary-data"
            make_package(src, {"word/document.xml": document, "word/media/image1.bin": untouched})

            report = normalize_ooxml(
                src,
                dst,
                options=NormalizationOptions(font_map=DEFAULT_LIBERATION_FONT_MAP),
            )

            self.assertEqual(report["document_kind"], "docx")
            self.assertEqual(report["emoji_replacements"]["🔴"], 1)
            with ZipFile(dst) as zf:
                output = zf.read("word/document.xml")
                self.assertIn("⬤".encode("utf-8"), output)
                self.assertIn(b'w:val="FF0000"', output)
                self.assertIn(b'"Liberation Sans"', output)
                self.assertEqual(zf.read("word/media/image1.bin"), untouched)

    def test_xlsx_font_mapping_without_content_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.xlsx"
            dst = td / "out.xlsx"
            styles = b'<styleSheet><font name="Arial"/><font name="Arial Unicode MS"/></styleSheet>'
            make_package(src, {"xl/workbook.xml": b"<workbook/>", "xl/styles.xml": styles})

            report = normalize_ooxml(
                src,
                dst,
                options=NormalizationOptions(font_map={"Arial": "Liberation Sans"}),
            )

            self.assertEqual(report["document_kind"], "xlsx")
            self.assertTrue(report["warnings"])
            with ZipFile(dst) as zf:
                output = zf.read("xl/styles.xml")
                self.assertIn(b'"Liberation Sans"', output)
                self.assertIn(b'"Arial Unicode MS"', output)

    def test_pptx_font_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.pptx"
            dst = td / "out.pptx"
            theme = b'<a:theme><a:latin typeface="Times New Roman"/></a:theme>'
            make_package(src, {"ppt/presentation.xml": b"<p:presentation/>", "ppt/theme/theme1.xml": theme})

            report = normalize_ooxml(
                src,
                dst,
                options=NormalizationOptions(font_map={"Times New Roman": "Liberation Serif"}),
            )

            self.assertEqual(report["document_kind"], "pptx")
            with ZipFile(dst) as zf:
                self.assertIn(b'"Liberation Serif"', zf.read("ppt/theme/theme1.xml"))

    def test_in_place_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "same.docx"
            make_package(path, {"word/document.xml": b"<w:document/>"})
            with self.assertRaises(ValueError):
                normalize_ooxml(path, path)


if __name__ == "__main__":
    unittest.main()
