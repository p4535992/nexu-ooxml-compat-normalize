# Licensing audit

This document records the project's distribution-oriented licensing review. It is an engineering/compliance checklist, not legal advice.

## Project license

Project-authored source code is MIT licensed.

## Current runtime/build components

| Component | Role | Upstream license model | Distribution note |
| --- | --- | --- | --- |
| Microsoft Open XML SDK | .NET structural validator | MIT | Retain license/copyright notice. |
| .NET self-contained runtime | Runtime for validator | Platform/product licensing plus exact third-party notices | Do not describe every .NET runtime distribution as simply MIT. The exact runtime pack license/third-party notice controls; Windows product distributions have Microsoft-specific product licensing, while Linux/macOS product distributions use MIT according to the .NET licensing model. |
| CPython | Python desktop runtime | PSF License v2 plus incorporated third-party licenses | Preserve the Python license/copyright notices for redistributed runtime content. |
| Tcl/Tk | Tkinter GUI runtime | permissive Tcl/Tk terms | Retain copyright notices and the Tcl/Tk license notice in distributions containing Tcl/Tk. |
| PyInstaller | bundler | GPL-2.0-or-later with PyInstaller bootloader exception (plus some Apache-2.0 files) | The bootloader exception permits distributing generated application bundles under the application's license, subject to dependency licenses. |
| Apache POI 5.5.1 | Java OOXML parser | Apache-2.0 | Retain Apache license/NOTICE material supplied by the dependency. |
| docx4j 17.1.0 | Java OOXML parser/model | Apache-2.0 | Retain Apache license/NOTICE material supplied by the dependency. |
| Quarkus 3.39.3 | local Java web/API wrapper | Apache-2.0 for Quarkus; transitives under their own licenses | Do not assume all transitive dependencies have the same license; generate an exact dependency/SBOM inventory for releases. |
| Eclipse Temurin/OpenJDK 17 | Java runtime / Docker runtime | OpenJDK and Temurin distributions contain multiple applicable license/notice sets | Preserve the exact runtime `legal/` material and upstream notices from the build/image actually distributed. |

## Current assessment

No dependency currently identified forces the project's own MIT source code to be relicensed merely because the project links to or runs with that dependency.

The main compliance risk is **distribution metadata**, not the project source license: portable artifacts bundle runtimes and transitive libraries, so release archives must preserve the relevant license and notice material for those exact binaries.

## Java SBOM result

The CI workflow `.github/workflows/license-audit.yml` generates CycloneDX 1.6 JSON SBOMs plus Maven dependency trees.

For the `0.4.0-rc.8` dependency graph the generated metadata reported:

- Java core: **42 components** — Apache-2.0, BSD-family and MIT metadata only;
- Quarkus application: **156 components** — mostly Apache-2.0, plus BSD/MIT, EPL-1.0/EPL-2.0 and GPL-2.0 **with the Classpath Exception**;
- no component in that run lacked license metadata in the generated SBOM;
- no plain GPL-without-exception or AGPL license was reported by the generated Maven/CycloneDX metadata.

The EPL/GPL-with-Classpath entries are primarily multi/dual-licensed framework/API dependencies. Examples in the audited graph include Vert.x artifacts declaring Apache-2.0 together with EPL, and Jakarta API/Parsson artifacts declaring EPL-2.0 and/or GPL-2.0 with the Classpath Exception. Their exact upstream terms remain authoritative.

This SBOM result is evidence for the reviewed dependency graph, not a permanent guarantee: it must be regenerated whenever dependency versions change.

## Shaded/uber-JAR notice handling

Maven Shade currently reports overlapping resources such as `META-INF/LICENSE`, `LICENSE.txt`, `LICENSE.md`, `NOTICE.txt`, `NOTICE.md` and `DEPENDENCIES` across transitive JARs. When duplicate resources collide, a shaded JAR can keep only one resource unless an explicit transformer/packaging strategy handles them.

Therefore **the shaded/uber JAR must not be treated as the sole authoritative carrier of third-party license notices**. Release compliance should rely on:

- external project third-party notice/license files;
- generated SBOM/dependency inventory;
- exact upstream license/NOTICE material where redistribution requires it;
- runtime `legal/` material for Temurin/OpenJDK.

Before a stable release, the Java release packaging should include or publish the generated SBOMs and a deterministic dependency-license bundle/report so notice preservation does not depend on colliding `META-INF` resources inside a fat JAR.

## Required before stable release

1. Keep `LICENSE`, `THIRD_PARTY_NOTICES.md` and `THIRD_PARTY_LICENSES.md` in every portable distribution.
2. Preserve the `legal/` directory from every `jlink`/Temurin runtime image.
3. Capture the exact .NET runtime-pack license and third-party notice used by each self-contained build, especially the Windows runtime pack.
4. Include the Python/PSF and Tcl/Tk license notices in desktop portable distributions containing those runtimes.
5. Generate and retain an SBOM/dependency inventory for the Java core and Quarkus artifacts so transitive licenses can be reviewed release-by-release.
6. Do not rely only on fat-JAR `META-INF/LICENSE*`/`NOTICE*` resources; publish/preserve a deterministic external dependency-license bundle or report.
7. Do not redistribute fonts unless their individual licenses explicitly permit the intended redistribution/embedding.
8. Do not add third-party OOXML test documents to the repository/release unless the file has a clear redistributable license or was generated by this project from project-owned content.

## Docker

The repository's Docker workflow builds the application image locally from Docker Official Maven/Temurin images. The project does not currently publish a prebuilt Docker image.

The final local image contains the project's MIT license summaries and inherits the upstream Temurin/OpenJDK runtime legal material from the base image. If a prebuilt image is published in the future, its exact base-image licenses/notices and Java dependency inventory must be treated as release artifacts as well.

## Test corpus policy

Public availability is not a license. Attachments from forums, bug trackers and document-sharing sites should not be committed or redistributed unless their license/provenance clearly permits it.

Preferred reusable sources are project-owned generated fixtures or upstream repositories with explicit permissive licenses, with per-fixture provenance recorded. See `docs/test-corpus-policy.md`.
