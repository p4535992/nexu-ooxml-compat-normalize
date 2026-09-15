# Licensing and third-party components

The project source code is licensed under the MIT License.

## Runtime dependencies

Version 0.1.0 has **no third-party Python runtime dependencies**. It uses Python's standard library (`zipfile`, `re`, `hashlib`, `json`, and related modules).

## Office suites

LibreOffice, ONLYOFFICE and Microsoft Office are compatibility targets, not linked or redistributed dependencies. The normalizer does not invoke or bundle their binaries.

## Fonts

The built-in optional mapping refers to the font family names `Liberation Serif`, `Liberation Sans` and `Liberation Mono`, but the project does **not** distribute font files.

Liberation Fonts are a separate project distributed under the SIL Open Font License. Users are responsible for installing fonts appropriate to their target environment. Merely writing a font family name into an OOXML document does not redistribute the font program.

## Future libraries

If Open XML SDK, OpenXmlPowerTools, or another library is added later, its license and transitive dependencies must be recorded here before release. The current implementation intentionally avoids those dependencies so the core normalizer remains small and auditable.
