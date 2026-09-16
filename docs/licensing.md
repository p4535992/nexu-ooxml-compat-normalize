# Licensing and third-party components

The project source code is licensed under the **MIT License**.

The portable binaries are intentionally built from free/open-source components. The goal is to keep the normalizer redistributable without requiring proprietary office-suite libraries.

## Normalization engine

The package-preserving normalization engine is Python code from this project and uses the Python standard library for ZIP/OPC handling, XML inspection, hashing, CLI and the Tkinter GUI.

Python is distributed under the Python Software Foundation License. Tk/Tcl components used by Tkinter have permissive Tcl/Tk licensing terms.

## Microsoft Open XML SDK

Portable builds bundle a small self-contained .NET helper that references **DocumentFormat.OpenXml (Microsoft Open XML SDK)**.

Open XML SDK is MIT licensed. It is used as an independent structural validator for DOCX, XLSX and PPTX before and after our own loss-averse normalization rules. It is **not** used to perform an editor-style open/save round-trip.

The helper is published self-contained, so an end user does not need to install .NET separately.

## .NET runtime

The self-contained helper includes the .NET runtime components required by the selected Runtime Identifier (for example `win-x64` or `linux-x64`). .NET runtime source is MIT licensed and the distribution carries additional third-party notices from the .NET project. Release engineering should retain the applicable notices for the exact .NET version used by the build.

## PyInstaller

PyInstaller is used to produce the final one-file GUI application and bundles the Python runtime plus the self-contained Open XML SDK helper.

PyInstaller is GPLv2 with a **special bootloader exception** intended to allow applications built with PyInstaller to be distributed under the application's own license. Always retain/check the authoritative license shipped with the exact PyInstaller version used by a release.

PyInstaller does not require this project itself to become GPL merely because it is used to create the executable, subject to the upstream exception terms.

## Office suites

LibreOffice, ONLYOFFICE and Microsoft Office are compatibility targets, not linked or redistributed dependencies. The normalizer does not require their binaries to perform its package normalization.

## Fonts

Font programs are not bundled. The normalizer preserves font names by default and can optionally write explicit alternative family names into OOXML.

Deployers remain responsible for installing target fonts and complying with their licenses. Future font-embedding support must check embedding rights before embedding a font program in an OOXML package.

## Development/test candidates

OpenXmlPowerTools (MIT), Apache POI (Apache-2.0) and docx4j (Apache-2.0) may be used in future as additional cross-parser or regression-test tools. They are not runtime dependencies of the current portable build.
