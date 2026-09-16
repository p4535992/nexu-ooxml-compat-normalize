# OOXML test corpus policy

The normalizer benefits from real-world DOCX/XLSX/PPTX regression files, but public availability alone is not sufficient permission to redistribute a document.

## Preferred fixture sources

Use these sources in order of preference:

1. **Project-generated fixtures** built from project-owned text/images and minimal OOXML packages.
2. **Generated fixtures from permissively licensed libraries**, keeping provenance and the upstream license notice where applicable.
3. **Upstream test fixtures from repositories with an explicit permissive repository/file license**, after checking that the specific binary fixture is not marked as third-party or subject to separate terms.
4. **Public forum/bug-tracker attachments only for local/manual investigation**, unless the attachment has an explicit redistributable license.

## Candidate upstream projects

The following projects are useful candidates because their repositories have explicit permissive licenses. A candidate repository license does not automatically prove that every binary fixture has the same provenance, so each imported file must still be checked before committing it.

- `python-openxml/python-docx` — MIT — DOCX generation/parsing fixtures.
- `scanny/python-pptx` — MIT — PPTX generation/parsing fixtures.
- `openpyxl/openpyxl` — MIT — XLSX generation/parsing fixtures.
- Apache POI — Apache-2.0 — DOCX/XLSX/PPTX parser regression material.
- Microsoft Open XML SDK — MIT — OOXML samples and generated examples.

## Required metadata for imported binary fixtures

Every committed third-party OOXML fixture should have a sidecar entry (for example in `tests/corpus/MANIFEST.md`) recording:

- local filename;
- upstream project/source;
- exact source URL or commit;
- original filename;
- license/SPDX identifier;
- copyright/attribution requirements;
- reason the fixture is useful;
- whether the file is redistributed verbatim or modified.

## Forum and bug-tracker files

Do not commit a forum/bug-tracker attachment merely because it is downloadable without authentication. If there is no explicit license, keep it outside the repository and use it only for temporary/manual compatibility testing where legally appropriate.

If such a file reveals a reproducible interoperability bug, create a new minimal project-owned fixture that reproduces the same OOXML structure without copying the original document content.

## Privacy

Before committing any document, inspect package metadata and embedded parts for author names, comments, tracked changes, thumbnails, custom XML, hidden sheets/slides, document properties and other personal or confidential data.
