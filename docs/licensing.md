# Licensing and third-party components

The project source code is licensed under the **MIT License**.

Release artifacts are intentionally built from free/open-source components. The goal is to keep the normalizer redistributable without requiring proprietary office-suite libraries.

## Python/Desktop normalization engine

The package-preserving Python normalization engine uses the Python standard library for ZIP/OPC handling, XML inspection, hashing, CLI and the Tkinter GUI.

Python is distributed under the Python Software Foundation License. Tk/Tcl components used by Tkinter have permissive Tcl/Tk licensing terms.

## Microsoft Open XML SDK and .NET

Desktop portable builds bundle a small self-contained .NET helper referencing **DocumentFormat.OpenXml (Microsoft Open XML SDK)**.

Open XML SDK is MIT licensed and is used as an independent structural validator before and after normalization. The self-contained .NET runtime is MIT licensed together with the applicable .NET third-party notices.

## PyInstaller

PyInstaller produces the one-file desktop application. It is GPLv2 with the PyInstaller bootloader exception that permits distributing bundled applications under the application's own license, subject to the authoritative upstream terms.

## Java core

The Java core is MIT-licensed project code. It uses:

- **Apache POI 5.5.1** — Apache License 2.0;
- **docx4j 17.1.0** — Apache License 2.0;
- Maven-resolved transitive dependencies under their respective open-source licenses.

POI and docx4j are used for independent pre-flight/post-flight parsing. The writer remains package-preserving and does not re-save the document through their high-level models.

The Maven build creates a normal library JAR and a shaded executable JAR. The release publishes the executable JAR as `ooxml-compat-normalize-java.jar`.

## Quarkus local service

The Quarkus module is MIT-licensed project code using **Quarkus 3.39.3**, which is Apache License 2.0, plus Quarkus REST/Jackson and their compatible open-source transitive dependencies.

The release publishes a single executable Quarkus uber-JAR named `ooxml-compat-normalize-quarkus.jar`. The service delegates all normalization to the Java core and binds to localhost by default.

## Java portable runtime

Windows/Linux Java portable archives contain both Java JARs plus a platform-specific runtime image created with `jlink` from Eclipse Temurin/OpenJDK 17.

OpenJDK/Temurin runtime code is distributed under **GPL-2.0 with the Classpath Exception**, together with third-party notices applicable to the exact runtime build. The Classpath Exception allows applications to use/link the Java class libraries without changing this project's MIT source-code license.

Redistributed runtime images must retain the authoritative OpenJDK/Temurin license and third-party notices that apply to the exact build used by CI.

## Office suites

LibreOffice, ONLYOFFICE and Microsoft Office are compatibility peers/targets, not linked or redistributed dependencies. The normalizer does not require their binaries to perform package normalization.

## Fonts

Font programs are not bundled. The normalizer preserves font names by default and can optionally write explicit alternative family names into OOXML.

Deployers remain responsible for installing target fonts and complying with their licenses. Future font-embedding support must check embedding rights before embedding a font program in an OOXML package.

## Additional research/test tooling

OpenXmlPowerTools (MIT) may still be used as an additional regression/research tool, but is not currently a runtime dependency.
