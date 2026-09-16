# Third-party notices

This project source is MIT licensed. Portable builds can bundle the following free/open-source components.

## Microsoft Open XML SDK

- Component: `DocumentFormat.OpenXml`
- Purpose: independent DOCX/XLSX/PPTX structural validation
- License: MIT
- Runtime model: linked into a self-contained .NET validator helper embedded in the portable application

## .NET runtime

- Purpose: self-contained runtime for the Open XML SDK validator helper
- License: MIT plus third-party notices applicable to the exact runtime build
- End-user installation required: no

## Python / Tcl/Tk

- Purpose: normalization engine and desktop GUI
- Python license: Python Software Foundation License
- Tcl/Tk: permissive Tcl/Tk license terms

## PyInstaller

- Purpose: build the single-file portable executable
- License: GPLv2 with the PyInstaller bootloader exception for bundled applications

The authoritative license texts and notices are those shipped by the exact component versions used to produce a release.

## Not bundled

LibreOffice, ONLYOFFICE, Microsoft Office and font binaries are not redistributed by this project. Optional font mapping only writes font family names into OOXML.
