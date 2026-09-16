# Java companion normalizer

This directory contains a standalone Java implementation of the conservative OOXML normalization layer.

It is **not** a wrapper around the Python executable. The JAR reads and writes DOCX/XLSX/PPTX OPC packages directly and uses two independent open-source Java OOXML libraries for pre-flight/post-flight parsing:

- **Apache POI 5.5.1** — Apache License 2.0; cross-format OPC/OOXML parser.
- **docx4j 17.1.0** — Apache License 2.0; independent OOXML package/model parser.

The actual writer remains package-preserving and surgical: unknown parts are copied rather than re-saved through a high-level document model.

## Build

Requires JDK 17+ and Maven 3.9+.

```bash
mvn -f java/pom.xml clean verify package
```

The shaded standalone artifact is:

```text
java/target/ooxml-compat-normalize-java.jar
```

## Usage

Audit a document with both Java parsers:

```bash
java -jar ooxml-compat-normalize-java.jar document.docx --audit-only
```

Conservative normalization; font identities are preserved by default:

```bash
java -jar ooxml-compat-normalize-java.jar input.docx output.docx
```

Explicit compatibility font profile:

```bash
java -jar ooxml-compat-normalize-java.jar input.xlsx output.xlsx --font-profile compat
```

Custom mapping:

```bash
java -jar ooxml-compat-normalize-java.jar input.pptx output.pptx \
  --font-map 'Old Font=New Font'
```

Profiles use the same names as the main project:

- `preserve-v1`
- `interop-transitional-v1`
- `portable-explicit-v1`

The Java companion currently implements the package-preserving/font/semantic-color layer. Advanced `portable-explicit-v1` theme/default materialization is still being ported and cross-tested against the Python engine; the CLI reports this rather than silently claiming full parity.

## Interoperability model

The JAR follows the same **N -> normalized OOXML -> N** model. There is no preferred source or target office suite.

```text
LibreOffice ----┐                         ┌---- LibreOffice
ONLYOFFICE -----┤                         ├---- ONLYOFFICE
Microsoft Office├--> normalized OOXML --->├---- Microsoft Office
other OOXML ----┘                         └---- other OOXML
```

## Licensing

The Java companion source is MIT, like the rest of this repository. Apache POI and docx4j are Apache License 2.0. The release JAR is shaded and therefore includes transitive open-source dependencies; their upstream `META-INF` notices/licenses and the repository third-party notices must be retained when redistributing the JAR.
