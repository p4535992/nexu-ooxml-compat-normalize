from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

from ooxml_compat_normalize.analysis import analyze_ooxml
from ooxml_compat_normalize.normalizer import (
    DEFAULT_LIBERATION_FONT_MAP,
    NormalizationError,
    NormalizationOptions,
    normalize_ooxml,
)
from ooxml_compat_normalize.package import DocumentKind, detect_document_kind
from ooxml_compat_normalize.profile import FontPolicy, INTEROP_TRANSITIONAL_V1, LossPolicy


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


class AnalysisTests(unittest.TestCase):
    def test_preflight_finds_producer_fonts_symbols_and_risks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "in.docx"
            document = (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:r><w:rPr><w:rFonts w:ascii="Arial"/></w:rPr><w:t>🔴</w:t></w:r>'
                '<w:altChunk r:id="rId1" xmlns:r="urn:r"/>'
                '</w:document>'
            ).encode()
            make_package(
                path,
                {
                    "word/document.xml": document,
                    "word/_rels/document.xml.rels": b"<Relationships/>",
                    "docProps/app.xml": b"<Properties><Application>LibreOffice/26.2</Application></Properties>",
                },
            )
            analysis = analyze_ooxml(path).to_dict()
            self.assertEqual(analysis["producer"], "LibreOffice/26.2")
            self.assertEqual(analysis["conformance"], "transitional")
            self.assertIn("Arial", analysis["required_fonts"])
            self.assertEqual(analysis["semantic_color_symbols"]["🔴"], 1)
            self.assertTrue(any(r["code"] == "altchunk" for r in analysis["risks"]))


class NormalizeTests(unittest.TestCase):
    def test_docx_symbol_and_font_mapping_are_surgical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.docx"
            dst = td / "out.docx"
            document = (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                '<w:r><w:rPr></w:rPr><w:t xml:space="preserve">🔴 </w:t></w:r>'
                '<w:r><w:rPr><w:rFonts w:ascii="Arial"/></w:rPr><w:t>Hello</w:t></w:r>'
                '</w:body></w:document>'
            ).encode("utf-8")
            untouched = b"unchanged-binary-data"
            rels = b"<Relationships><Relationship Id=\"rId1\"/></Relationships>"
            content_types = b"<Types/>"
            make_package(
                src,
                {
                    "[Content_Types].xml": content_types,
                    "word/document.xml": document,
                    "word/_rels/document.xml.rels": rels,
                    "word/media/image1.bin": untouched,
                },
            )

            report = normalize_ooxml(
                src,
                dst,
                options=NormalizationOptions(font_map=DEFAULT_LIBERATION_FONT_MAP),
            )

            self.assertEqual(report["document_kind"], "docx")
            self.assertEqual(report["semantic_color_symbol_replacements"]["🔴"], 1)
            self.assertEqual(report["preservation_checks"]["zip_integrity"], "ok")
            with ZipFile(dst) as zf:
                output = zf.read("word/document.xml")
                self.assertIn("●".encode("utf-8"), output)
                self.assertIn(b'w:val="FF0000"', output)
                self.assertIn(b'"Liberation Sans"', output)
                self.assertEqual(zf.read("word/media/image1.bin"), untouched)
                self.assertEqual(zf.read("word/_rels/document.xml.rels"), rels)
                self.assertEqual(zf.read("[Content_Types].xml"), content_types)

    def test_pptx_semantic_color_uses_drawingml_srgb(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.pptx"
            dst = td / "out.pptx"
            slide = (
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:r><a:t>🟢 </a:t></a:r></p:sld>'
            ).encode("utf-8")
            make_package(src, {"ppt/presentation.xml": b"<p:presentation/>", "ppt/slides/slide1.xml": slide})
            report = normalize_ooxml(src, dst)
            self.assertEqual(report["semantic_color_symbol_replacements"]["🟢"], 1)
            with ZipFile(dst) as zf:
                output = zf.read("ppt/slides/slide1.xml")
                self.assertIn(b'<a:srgbClr val="00B050"/>', output)
                self.assertIn("●".encode(), output)

    def test_xlsx_rich_text_semantic_color(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.xlsx"
            dst = td / "out.xlsx"
            shared = (
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<si><r><t>🟡 </t></r></si></sst>'
            ).encode("utf-8")
            make_package(src, {"xl/workbook.xml": b"<workbook/>", "xl/sharedStrings.xml": shared})
            report = normalize_ooxml(src, dst)
            self.assertEqual(report["semantic_color_symbol_replacements"]["🟡"], 1)
            with ZipFile(dst) as zf:
                output = zf.read("xl/sharedStrings.xml")
                self.assertIn(b'<color rgb="FFFFC000"/>', output)
                self.assertIn("●".encode(), output)

    def test_xlsx_plain_string_is_reported_not_destructively_rebuilt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.xlsx"
            dst = td / "out.xlsx"
            shared = b'<sst><si><t>\xf0\x9f\x94\xb4</t></si></sst>'
            make_package(src, {"xl/workbook.xml": b"<workbook/>", "xl/sharedStrings.xml": shared})
            report = normalize_ooxml(src, dst)
            self.assertIn("🔴", report["postflight"]["semantic_color_symbols"])
            self.assertTrue(any("remain" in w for w in report["warnings"]))

    def test_strict_font_inventory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.docx"
            dst = td / "out.docx"
            doc = (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:rFonts w:ascii="Rare Corporate Font"/></w:document>'
            ).encode()
            make_package(src, {"word/document.xml": doc})
            profile = replace(
                INTEROP_TRANSITIONAL_V1,
                loss_policy=LossPolicy.STRICT,
                font_policy=FontPolicy.REQUIRE_AVAILABLE,
            )
            with self.assertRaises(NormalizationError):
                normalize_ooxml(
                    src,
                    dst,
                    options=NormalizationOptions(profile=profile, available_fonts=frozenset({"Arial"})),
                )

    def test_strict_rejects_high_risk_altchunk(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.docx"
            dst = td / "out.docx"
            doc = (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:altChunk r:id="rId1" xmlns:r="urn:r"/></w:document>'
            ).encode()
            make_package(src, {"word/document.xml": doc})
            profile = replace(INTEROP_TRANSITIONAL_V1, loss_policy=LossPolicy.STRICT)
            with self.assertRaises(NormalizationError):
                normalize_ooxml(src, dst, options=NormalizationOptions(profile=profile))

    def test_font_mapping_never_rewrites_user_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "in.docx"
            dst = td / "out.docx"
            doc = (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:r><w:rPr><w:rFonts w:ascii="Arial"/></w:rPr>'
                '<w:t>The literal value "Arial" must remain text.</w:t></w:r></w:document>'
            ).encode()
            make_package(src, {"word/document.xml": doc})
            normalize_ooxml(
                src,
                dst,
                options=NormalizationOptions(font_map={"Arial": "Liberation Sans"}),
            )
            with ZipFile(dst) as zf:
                output = zf.read("word/document.xml")
                self.assertIn(b'w:ascii="Liberation Sans"', output)
                self.assertIn(b'The literal value "Arial" must remain text.', output)

    def test_in_place_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "same.docx"
            make_package(path, {"word/document.xml": b"<w:document/>"})
            with self.assertRaises(ValueError):
                normalize_ooxml(path, path)


if __name__ == "__main__":
    unittest.main()


class PortableExplicitProfileTests(unittest.TestCase):
    THEME = b'''<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
      <a:themeElements>
        <a:clrScheme name="Test">
          <a:dk1><a:srgbClr val="000000"/></a:dk1>
          <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
          <a:dk2><a:srgbClr val="222222"/></a:dk2>
          <a:lt2><a:srgbClr val="EEEEEE"/></a:lt2>
          <a:accent1><a:srgbClr val="112233"/></a:accent1>
          <a:accent2><a:srgbClr val="445566"/></a:accent2>
          <a:accent3><a:srgbClr val="778899"/></a:accent3>
          <a:accent4><a:srgbClr val="AABBCC"/></a:accent4>
          <a:accent5><a:srgbClr val="123456"/></a:accent5>
          <a:accent6><a:srgbClr val="654321"/></a:accent6>
          <a:hlink><a:srgbClr val="0000FF"/></a:hlink>
          <a:folHlink><a:srgbClr val="800080"/></a:folHlink>
        </a:clrScheme>
        <a:fontScheme name="Test">
          <a:majorFont><a:latin typeface="Major Sans"/><a:ea typeface="Major EA"/><a:cs typeface="Major CS"/></a:majorFont>
          <a:minorFont><a:latin typeface="Minor Sans"/><a:ea typeface="Minor EA"/><a:cs typeface="Minor CS"/></a:minorFont>
        </a:fontScheme>
      </a:themeElements>
    </a:theme>'''

    def test_docx_materializes_theme_and_table_default(self) -> None:
        from ooxml_compat_normalize.profile import PORTABLE_EXPLICIT_V1
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src, dst = td / "in.docx", td / "out.docx"
            doc = b'''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
              <w:p><w:r><w:rPr><w:rFonts w:asciiTheme="minorHAnsi" w:hAnsiTheme="minorHAnsi"/><w:color w:themeColor="accent1"/></w:rPr><w:t>Hello</w:t></w:r></w:p>
              <w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl>
            </w:body></w:document>'''
            make_package(src, {"word/document.xml": doc, "word/theme/theme1.xml": self.THEME})
            report = normalize_ooxml(src, dst, options=NormalizationOptions(profile=PORTABLE_EXPLICIT_V1))
            self.assertGreater(report["portability_rule_applications"]["docx_theme_fonts"], 0)
            self.assertGreater(report["portability_rule_applications"]["docx_theme_colors"], 0)
            self.assertEqual(report["portability_rule_applications"]["docx_table_layout_defaults"], 1)
            with ZipFile(dst) as zf:
                out = zf.read("word/document.xml")
                self.assertIn(b'w:ascii="Minor Sans"', out)
                self.assertNotIn(b'asciiTheme=', out)
                self.assertIn(b'w:val="112233"', out)
                self.assertNotIn(b'themeColor=', out)
                self.assertIn(b'<w:tblLayout w:type="autofit"/>', out)

    def test_xlsx_materializes_theme_and_anchor_default(self) -> None:
        from ooxml_compat_normalize.profile import PORTABLE_EXPLICIT_V1
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src, dst = td / "in.xlsx", td / "out.xlsx"
            styles = b'''<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><scheme val="minor"/><color theme="4"/></font></fonts></styleSheet>'''
            drawing = b'''<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"><xdr:twoCellAnchor><xdr:from/><xdr:to/></xdr:twoCellAnchor></xdr:wsDr>'''
            make_package(src, {
                "xl/workbook.xml": b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
                "xl/styles.xml": styles,
                "xl/theme/theme1.xml": self.THEME,
                "xl/drawings/drawing1.xml": drawing,
            })
            report = normalize_ooxml(src, dst, options=NormalizationOptions(profile=PORTABLE_EXPLICIT_V1))
            self.assertEqual(report["portability_rule_applications"]["xlsx_theme_fonts"], 1)
            self.assertEqual(report["portability_rule_applications"]["xlsx_theme_colors"], 1)
            self.assertEqual(report["portability_rule_applications"]["xlsx_anchor_defaults"], 1)
            with ZipFile(dst) as zf:
                out = zf.read("xl/styles.xml")
                self.assertIn(b'<name val="Minor Sans"/>', out)
                self.assertNotIn(b'<scheme val="minor"/>', out)
                self.assertIn(b'rgb="FF112233"', out)
                drawing_out = zf.read("xl/drawings/drawing1.xml")
                self.assertIn(b'editAs="twoCell"', drawing_out)

    def test_pptx_materializes_simple_theme_references(self) -> None:
        from ooxml_compat_normalize.profile import PORTABLE_EXPLICIT_V1
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src, dst = td / "in.pptx", td / "out.pptx"
            slide = b'''<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><a:r><a:rPr><a:latin typeface="+mn-lt"/><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:rPr><a:t>Hello</a:t></a:r><a:bodyPr></a:bodyPr></p:cSld></p:sld>'''
            make_package(src, {
                "ppt/presentation.xml": b'<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
                "ppt/slides/slide1.xml": slide,
                "ppt/theme/theme1.xml": self.THEME,
            })
            pre = analyze_ooxml(src).to_dict()
            self.assertEqual(pre["diagnostics"]["text_bodies_with_implicit_autofit"], 1)
            report = normalize_ooxml(src, dst, options=NormalizationOptions(profile=PORTABLE_EXPLICIT_V1))
            with ZipFile(dst) as zf:
                out = zf.read("ppt/slides/slide1.xml")
                self.assertIn(b'typeface="Minor Sans"', out)
                self.assertIn(b'<a:srgbClr val="112233"/>', out)
                self.assertNotIn(b'<a:schemeClr val="accent1"/>', out)

    def test_word_style_inheritance_cycle_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "styles.docx"
            styles = b'''<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:style w:type="paragraph" w:styleId="A"><w:basedOn w:val="B"/></w:style>
              <w:style w:type="paragraph" w:styleId="B"><w:basedOn w:val="A"/></w:style>
            </w:styles>'''
            make_package(path, {"word/document.xml": b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>', "word/styles.xml": styles})
            analysis = analyze_ooxml(path).to_dict()
            self.assertTrue(analysis["diagnostics"]["style_inheritance_cycles"])
            self.assertTrue(any(r["code"] == "style-inheritance-cycle" for r in analysis["risks"]))

    def test_xlsx_number_format_and_conditional_format_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "formats.xlsx"
            styles = b'''<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="2"><numFmt numFmtId="200" formatCode="x"/><numFmt numFmtId="200" formatCode="y"/></numFmts><cellXfs count="1"><xf numFmtId="201"/></cellXfs></styleSheet>'''
            sheet = b'''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><conditionalFormatting sqref="A1"><cfRule type="expression" priority="1"/><cfRule type="expression" priority="1"/></conditionalFormatting></worksheet>'''
            make_package(path, {"xl/workbook.xml": b'<workbook/>', "xl/styles.xml": styles, "xl/worksheets/sheet1.xml": sheet})
            analysis = analyze_ooxml(path).to_dict()
            self.assertEqual(analysis["diagnostics"]["duplicate_custom_number_format_ids"], [200])
            self.assertEqual(analysis["diagnostics"]["missing_custom_number_format_references"], [201])
            self.assertEqual(analysis["diagnostics"]["duplicate_conditional_format_priorities"], [1])

class PptxThemeInheritanceTests(unittest.TestCase):
    def test_slide_resolves_theme_via_layout_and_master(self) -> None:
        from ooxml_compat_normalize.profile import PORTABLE_EXPLICIT_V1
        theme1 = b'''<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:themeElements><a:clrScheme name="T1"><a:accent1><a:srgbClr val="111111"/></a:accent1></a:clrScheme><a:fontScheme name="F1"><a:majorFont><a:latin typeface="M1"/></a:majorFont><a:minorFont><a:latin typeface="Minor One"/></a:minorFont></a:fontScheme></a:themeElements></a:theme>'''
        theme2 = b'''<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:themeElements><a:clrScheme name="T2"><a:accent1><a:srgbClr val="ABCDEF"/></a:accent1></a:clrScheme><a:fontScheme name="F2"><a:majorFont><a:latin typeface="M2"/></a:majorFont><a:minorFont><a:latin typeface="Minor Two"/></a:minorFont></a:fontScheme></a:themeElements></a:theme>'''
        rels_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        slide_rels = f'''<Relationships xmlns="{rels_ns}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>'''.encode()
        layout_rels = f'''<Relationships xmlns="{rels_ns}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster2.xml"/></Relationships>'''.encode()
        master_rels = f'''<Relationships xmlns="{rels_ns}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme2.xml"/></Relationships>'''.encode()
        slide = b'''<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:rPr><a:latin typeface="+mn-lt"/><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:rPr><a:t>X</a:t></a:r></p:sld>'''
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src, dst = td / "multi.pptx", td / "out.pptx"
            make_package(src, {
                "ppt/presentation.xml": b'<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
                "ppt/slides/slide1.xml": slide,
                "ppt/slides/_rels/slide1.xml.rels": slide_rels,
                "ppt/slideLayouts/slideLayout1.xml": b'<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
                "ppt/slideLayouts/_rels/slideLayout1.xml.rels": layout_rels,
                "ppt/slideMasters/slideMaster2.xml": b'<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
                "ppt/slideMasters/_rels/slideMaster2.xml.rels": master_rels,
                "ppt/theme/theme1.xml": theme1,
                "ppt/theme/theme2.xml": theme2,
            })
            report = normalize_ooxml(src, dst, options=NormalizationOptions(profile=PORTABLE_EXPLICIT_V1))
            with ZipFile(dst) as zf:
                out = zf.read("ppt/slides/slide1.xml")
                self.assertIn(b'typeface="Minor Two"', out)
                self.assertIn(b'<a:srgbClr val="ABCDEF"/>', out)
            self.assertTrue(any("Multiple theme parts" in warning for warning in report["warnings"]))
