from __future__ import annotations

from enum import Enum


class DocumentKind(str, Enum):
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"


def detect_document_kind(names: set[str]) -> DocumentKind:
    if "word/document.xml" in names:
        return DocumentKind.DOCX
    if "xl/workbook.xml" in names:
        return DocumentKind.XLSX
    if "ppt/presentation.xml" in names:
        return DocumentKind.PPTX
    raise ValueError("Unsupported OOXML package: expected DOCX, XLSX, or PPTX")
