# Third-party license summary

This file is a distribution-oriented summary. It is **not** a substitute for the authoritative license/NOTICE files shipped by the exact dependency/runtime versions used in a build.

## Microsoft Open XML SDK (`DocumentFormat.OpenXml`)

License: MIT.

Copyright (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## .NET self-contained runtime

The .NET source repositories use MIT for source code, but binary/product/runtime-pack licensing depends on the distribution/platform. Microsoft documents Linux/macOS product distributions as MIT and Windows product distributions under the applicable .NET Library License, with third-party notices accompanying the exact runtime pack.

Portable builds must therefore retain the **exact runtime-pack license and third-party notice** applicable to the platform/version used by CI rather than relying on this summary alone.

## Python

CPython is licensed under the Python Software Foundation License Version 2. CPython also incorporates software/data under additional licenses; the authoritative Python license material for the exact redistributed Python version must be retained with desktop portable distributions.

## Tcl/Tk

Tcl/Tk uses permissive license terms that allow use, modification and redistribution provided existing copyright notices are retained and the applicable license notice is included in distributions.

## PyInstaller bootloader

PyInstaller is distributed under GPL-2.0-or-later with the PyInstaller bootloader exception for the bundled application path (and some PyInstaller files are Apache-2.0). The exception permits generated application bundles to use the application's own license, subject to the licenses of bundled dependencies.

## Apache POI 5.5.1

License: Apache License, Version 2.0.

Purpose in this project: Java-side OPC/OOXML parsing and cross-format validation for DOCX, XLSX and PPTX.

Upstream: https://poi.apache.org/

## docx4j 17.1.0

License: Apache License, Version 2.0 for docx4j project code.

Purpose in this project: second independent Java OOXML package/model parser used by the Java core for pre-flight/post-flight validation.

Upstream: https://www.docx4java.org/

Transitive libraries pulled by Maven keep their own licenses and notices.

## Quarkus 3.39.3

License: Apache License, Version 2.0 for the Quarkus project. Quarkus runtime extensions and their transitive dependencies retain their own upstream licenses.

Purpose in this project: local-only web UI and REST service wrapping the Java core normalizer.

Upstream: https://quarkus.io/

## Eclipse Temurin / OpenJDK 17

OpenJDK class-library/runtime code is commonly distributed under GPL-2.0 with the Classpath Exception, but a Temurin/OpenJDK binary distribution includes multiple applicable license and third-party notice sets.

Purpose in this project: platform-specific runtime image created with `jlink` and bundled inside the Windows/Linux Java portable archives; also the runtime base for local Docker builds.

The Classpath Exception permits ordinary application linking/use without imposing the GPL on this project's MIT source code. The exact runtime's `legal/` directory and upstream notices must remain with redistributed runtime images.

## Java shaded/uber artifacts

The executable Java core JAR and Quarkus uber-JAR contain Maven-resolved transitive dependencies under their own licenses. Upstream `META-INF` license/notice resources should be retained where supplied. A release-level SBOM/dependency inventory should be used to audit exact transitive licenses.

## Docker image

The repository currently builds the Docker image locally rather than publishing it as a release artifact. The final image is based on Eclipse Temurin 17 JRE and includes project license summaries under `/app/licenses`; upstream runtime legal material remains part of the base image.

If prebuilt container images are published later, the base-image/runtime and Java dependency license inventory must be published/reviewed with that image.

For the current compliance checklist, see `docs/licensing-audit.md`.
