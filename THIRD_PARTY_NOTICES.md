# Third-party notices

This project source is MIT licensed. Release artifacts can bundle the following free/open-source components.

## Microsoft Open XML SDK

- Component: `DocumentFormat.OpenXml`
- Purpose: independent DOCX/XLSX/PPTX structural validation in Windows/Linux desktop portable builds
- License: MIT

## .NET runtime

- Purpose: self-contained runtime for the Open XML SDK validator helper
- License: MIT plus third-party notices applicable to the exact runtime build
- End-user installation required: no

## Python / Tcl/Tk / PyInstaller

- Python: Python Software Foundation License
- Tcl/Tk: permissive Tcl/Tk license terms
- PyInstaller: GPLv2 with the PyInstaller bootloader exception for bundled applications
- Purpose: primary desktop engine/GUI and one-file Windows/Linux desktop distributions

## Apache POI

- Component: `org.apache.poi:poi-ooxml:5.5.1`
- Purpose: independent Java OPC/OOXML parsing of DOCX/XLSX/PPTX in the Java core
- License: Apache License 2.0
- Project: https://poi.apache.org/

## docx4j

- Components: `org.docx4j:docx4j-core:17.1.0` and `docx4j-JAXB-ReferenceImpl:17.1.0`
- Purpose: second independent Java OOXML package/model parser
- License: Apache License 2.0
- Project: https://www.docx4java.org/

## Quarkus

- Component family: Quarkus 3.39.3, including Quarkus REST Jackson and required runtime components
- Purpose: local web UI / REST wrapper around the Java core
- License: Apache License 2.0 for Quarkus; transitive dependencies remain under their respective compatible open-source terms
- Project: https://quarkus.io/

## Eclipse Temurin / OpenJDK 17 runtime

- Purpose: runtime bundled in the Windows/Linux Java portable archives produced with `jlink`
- License: GPL-2.0 with the Classpath Exception for OpenJDK/Temurin, together with applicable third-party notices
- End-user Java installation required: no for the Java portable archives

## Java artifact model

The release includes:

- an executable shaded Java core JAR;
- an executable Quarkus uber-JAR;
- Windows/Linux Java portable archives containing both JARs plus a platform-specific `jlink` runtime.

The Java JARs contain Maven-resolved transitive open-source dependencies. Upstream `META-INF` notices/license resources are retained where supplied. The portable runtime must retain the license/notices produced with the exact OpenJDK build used by the release workflow.

The authoritative license texts and notices are those shipped by the exact component versions used to produce a release.

## Not bundled

LibreOffice, ONLYOFFICE, Microsoft Office and font binaries are not redistributed by this project. Optional font mapping only writes font family names into OOXML.
