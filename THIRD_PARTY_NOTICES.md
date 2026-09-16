# Third-party notices

This project source is MIT licensed. Release artifacts can bundle the following free/open-source components.

## Microsoft Open XML SDK

- Component: `DocumentFormat.OpenXml`
- Purpose: independent DOCX/XLSX/PPTX structural validation in Windows/Linux portable builds
- License: MIT
- Runtime model: linked into a self-contained .NET validator helper embedded in the portable application

## .NET runtime

- Purpose: self-contained runtime for the Open XML SDK validator helper
- License: MIT plus third-party notices applicable to the exact runtime build
- End-user installation required: no

## Python / Tcl/Tk

- Purpose: primary normalization engine and desktop GUI
- Python license: Python Software Foundation License
- Tcl/Tk: permissive Tcl/Tk license terms

## PyInstaller

- Purpose: build the single-file Windows/Linux portable executable
- License: GPLv2 with the PyInstaller bootloader exception for bundled applications

## Apache POI

- Component: `org.apache.poi:poi-ooxml:5.5.1`
- Purpose: independent Java OPC/OOXML parsing of DOCX/XLSX/PPTX in the standalone JAR
- License: Apache License 2.0
- Project: https://poi.apache.org/

## docx4j

- Components: `org.docx4j:docx4j-core:17.1.0` and `docx4j-JAXB-ReferenceImpl:17.1.0`
- Purpose: second independent Java OOXML package/model parser in the standalone JAR
- License: Apache License 2.0
- Project: https://www.docx4java.org/

## Java runtime model

The release JAR is a shaded application. It contains Apache POI, docx4j and their Maven-resolved transitive open-source dependencies. Upstream `META-INF` notices/license resources are retained where supplied, and the Java module also ships a `THIRD-PARTY-NOTICES.txt` resource.

The authoritative license texts and notices are those shipped by the exact component versions used to produce a release.

## Not bundled

LibreOffice, ONLYOFFICE, Microsoft Office and font binaries are not redistributed by this project. Optional font mapping only writes font family names into OOXML.
