# Third-party notices

This project source is MIT licensed. Release artifacts and locally built container images can bundle the following free/open-source components.

## Microsoft Open XML SDK

- Component: `DocumentFormat.OpenXml`
- Purpose: independent DOCX/XLSX/PPTX structural validation in Windows/Linux desktop portable builds and the Python Docker image
- License: MIT

## .NET self-contained runtime

- Purpose: runtime for the Open XML SDK validator helper used by desktop portable builds and the Python Docker image
- Licensing: exact product/runtime-pack license plus third-party notices for the platform/build used by CI or the Docker build stage
- Important: do not treat every .NET product/runtime distribution as universally MIT; Microsoft documents different product-distribution licensing for Windows versus Linux/macOS
- Python Docker: validator build license and `ThirdPartyNotices.txt` are copied to `/app/licenses/dotnet/`
- End-user installation required: no

## Python / Tcl/Tk / PyInstaller

- CPython: Python Software Foundation License Version 2 plus incorporated third-party licenses/notices
- Tcl/Tk: permissive Tcl/Tk license terms; notices must be retained in redistributed copies
- PyInstaller: GPL-2.0-or-later with the PyInstaller bootloader exception for bundled applications (with some files under Apache-2.0)
- Purpose: primary Python engine, local HTTP/REST service, desktop GUI and one-file Windows/Linux desktop distributions

## Apache POI

- Component: `org.apache.poi:poi-ooxml:5.5.1`
- Purpose: independent Java OPC/OOXML parsing of DOCX/XLSX/PPTX in the Java core
- License: Apache License 2.0
- Project: https://poi.apache.org/

## docx4j

- Components: `org.docx4j:docx4j-core:17.1.0` and `docx4j-JAXB-ReferenceImpl:17.1.0`
- Purpose: second independent Java OOXML package/model parser
- License: Apache License 2.0 for docx4j project code; transitive dependencies retain their own licenses
- Project: https://www.docx4java.org/

## Quarkus

- Component family: Quarkus 3.39.3, including Quarkus REST Jackson and required runtime components
- Purpose: local web UI / REST wrapper around the Java core
- License: Apache License 2.0 for Quarkus project code; transitive dependencies retain their own licenses
- Project: https://quarkus.io/

## Eclipse Temurin / OpenJDK 17 runtime

- Purpose: runtime bundled in the Windows/Linux Java portable archives produced with `jlink`, and runtime used by the local Java Docker image
- Licensing: OpenJDK/Temurin distributions contain multiple applicable license/notice sets; OpenJDK class-library/runtime code commonly uses GPL-2.0 with the Classpath Exception
- Required material: preserve the exact runtime `legal/` directory and upstream notices from the binary actually redistributed
- End-user Java installation required: no for the Java portable archives

## Java artifact model

The release includes:

- an executable shaded Java core JAR;
- an executable Quarkus uber-JAR;
- Windows/Linux Java portable archives containing both JARs plus a platform-specific `jlink` runtime.

The Java JARs contain Maven-resolved transitive dependencies under their own licenses. Upstream `META-INF` notices/license resources should be retained where supplied, and release review should use an exact SBOM/dependency inventory rather than assuming all transitives use the same license.

The portable runtime must retain the legal/notices produced with the exact OpenJDK/Temurin build used by the release workflow.

The authoritative license texts and notices are those shipped by the exact component versions used to produce a release.

## Docker

The repository provides two local stacks:

- `Dockerfile` + `docker-compose.java.yml` for the Java/Quarkus service;
- `Dockerfile.python` + `docker-compose.python.yml` for the Python HTTP/REST service with the self-contained Open XML SDK validator.

The project does not currently publish prebuilt Docker images. See `docker/README.md` and `docs/licensing-audit.md`.

## Not bundled

LibreOffice, ONLYOFFICE, Microsoft Office and font binaries are not redistributed by this project. Optional font mapping only writes font family names into OOXML.

Third-party forum/bug-tracker OOXML attachments are also not redistributed unless their license/provenance explicitly permits it.
