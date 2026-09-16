# Licensing and third-party components

The project source code is licensed under the **MIT License**.

Release artifacts are intentionally built from free/open-source components. The goal is to keep the normalizer redistributable without requiring proprietary office-suite libraries.

This document is an engineering/compliance summary, not legal advice. The authoritative terms are those shipped by the exact component/runtime build being redistributed. See also [`licensing-audit.md`](licensing-audit.md).

## Python/Desktop normalization engine

The package-preserving Python normalization engine uses the Python standard library for ZIP/OPC handling, XML inspection, hashing, CLI, the lightweight HTTP/REST service and the Tkinter GUI.

CPython is distributed under the Python Software Foundation License Version 2 together with licenses/notices for incorporated third-party software. Tk/Tcl components used by Tkinter have permissive Tcl/Tk licensing terms requiring preservation of their notices in redistributed copies.

## Microsoft Open XML SDK and .NET

Desktop portable builds and the Python Docker build bundle a small self-contained .NET helper referencing **DocumentFormat.OpenXml (Microsoft Open XML SDK)**.

Open XML SDK is MIT licensed and is used as an independent structural validator before and after normalization.

Do **not** describe every self-contained .NET runtime distribution as simply "MIT". Microsoft distinguishes source/package licensing from product/runtime-pack licensing. According to the .NET licensing model, Linux/macOS product distributions use MIT while Windows product distributions use the applicable .NET Library License; exact runtime packs also carry their own third-party notices. Portable releases should retain the license and third-party notice material applicable to the exact runtime pack used by CI.

The Python Docker image copies the .NET SDK/runtime license and `ThirdPartyNotices.txt` used by its validator build into `/app/licenses/dotnet/` so the locally built image retains that material alongside the project notices.

## PyInstaller

PyInstaller produces the one-file desktop application. It is GPLv2-or-later with the PyInstaller bootloader exception (with some files under Apache-2.0) that permits distributing bundled applications under the application's own license, subject to the licenses of the bundled dependencies.

## Java core

The Java core is MIT-licensed project code. It uses:

- **Apache POI 5.5.1** — Apache License 2.0;
- **docx4j 17.1.0** — Apache License 2.0;
- Maven-resolved transitive dependencies under their respective licenses.

POI and docx4j are used for independent pre-flight/post-flight parsing. The writer remains package-preserving and does not re-save the document through their high-level models.

The Maven build creates a normal library JAR and a shaded executable JAR. The release publishes the executable core as `OOXML-Compat-Normalize-java-core.jar`.

Because the shaded JAR contains transitive libraries, release compliance should be based on an exact dependency/SBOM inventory rather than assuming every transitive dependency is Apache-2.0.

## Quarkus local service

The Quarkus module is MIT-licensed project code using **Quarkus 3.39.3**, whose project license is Apache License 2.0, plus Quarkus REST/Jackson and their transitive dependencies under their respective licenses.

The release publishes a single executable Quarkus uber-JAR named `OOXML-Compat-Normalize-java-quarkus.jar`. The service delegates all normalization to the Java core and binds to localhost by default outside containers.

## Java portable runtime

Windows/Linux Java portable archives contain both Java JARs plus a platform-specific runtime image created with `jlink` from Eclipse Temurin/OpenJDK 17.

OpenJDK class-library/runtime code is commonly distributed under GPL-2.0 with the Classpath Exception, but a Temurin/OpenJDK binary distribution contains multiple applicable license and third-party notice sets. The exact runtime's `legal/` directory and upstream notices are authoritative for the binary actually redistributed.

The Classpath Exception prevents normal use/linking of the Java class libraries from forcing this project's MIT source code to become GPL. It does **not** remove the obligation to preserve the runtime's own licenses/notices when redistributing that runtime.

## Docker

The repository provides two local Docker Compose stacks:

- `docker-compose.java.yml` builds the Quarkus/Java service from Docker Official Maven/Temurin images;
- `docker-compose.python.yml` builds the Python HTTP/REST service from the official Python image and a .NET SDK build stage used to publish the Open XML SDK validator.

The project does not currently publish prebuilt Docker images. Java and Python images are built locally. Each final image contains the project's license summaries; the Java image inherits the Eclipse Temurin/OpenJDK runtime legal material from the base image, while the Python image preserves the .NET validator build license/third-party notice material under `/app/licenses/dotnet/`.

If prebuilt images are published later, the exact base-image/runtime licenses and dependency inventory must be treated as release artifacts.

## Office suites

LibreOffice, ONLYOFFICE and Microsoft Office are compatibility peers/targets, not linked or redistributed dependencies. The normalizer does not require their binaries to perform package normalization.

## Fonts

Font programs are not bundled. The normalizer preserves font names by default and can optionally write explicit alternative family names into OOXML.

Deployers remain responsible for installing target fonts and complying with their licenses. Future font-embedding support must check embedding rights before embedding a font program in an OOXML package.

## Test documents

Public availability is not a redistribution license. Forum and bug-tracker attachments should not be committed to the repository or release artifacts unless their provenance/license explicitly permits redistribution.

Prefer project-generated fixtures or files from explicitly permissive upstream projects, with per-fixture provenance/license metadata. See [`test-corpus-policy.md`](test-corpus-policy.md).

## Additional research/test tooling

OpenXmlPowerTools (MIT) may still be used as an additional regression/research tool, but is not currently a runtime dependency.
