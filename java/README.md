# Java core normalizer

This directory contains the Java implementation of the conservative OOXML normalization layer.

It is **not** a wrapper around the Python executable. The core reads and writes DOCX/XLSX/PPTX OPC packages directly and uses two independent open-source Java OOXML libraries for pre-flight/post-flight parsing:

- **Apache POI 5.5.1** — Apache License 2.0; cross-format OPC/OOXML parser.
- **docx4j 17.1.0** — Apache License 2.0; independent OOXML package/model parser.

The actual writer remains package-preserving and surgical: unknown parts are copied rather than re-saved through a high-level document model.

## Build

Requires JDK 17+ and Maven 3.9+.

```bash
mvn -f java/pom.xml clean install
```

The build produces:

```text
java/target/ooxml-compat-normalize-java.jar
    thin library JAR used by the Quarkus module

java/target/ooxml-compat-normalize-java-0.4.0-rc.9-all.jar
    shaded executable CLI JAR
```

The release workflow gives the executable core a deliberately explicit name:

```text
OOXML-Compat-Normalize-java-core.jar
```

## Usage

```bash
java -jar OOXML-Compat-Normalize-java-core.jar document.docx --audit-only
java -jar OOXML-Compat-Normalize-java-core.jar input.docx output.docx
java -jar OOXML-Compat-Normalize-java-core.jar input.xlsx output.xlsx --font-profile compat
java -jar OOXML-Compat-Normalize-java-core.jar input.pptx output.pptx --font-map 'Old Font=New Font'
```

Default font behavior is preserve: explicitly declared font identities are not changed unless a mapping policy is requested.

Profiles use the same names as the main project:

- `preserve-v1`
- `interop-transitional-v1`
- `portable-explicit-v1`

The Java core currently implements the package-preserving/font/semantic-color layer. Advanced `portable-explicit-v1` theme/default materialization is still being ported and cross-tested against the Python engine; the CLI reports this rather than silently claiming full parity.

## Interoperability model

The JAR follows the same **N → normalized OOXML → N** model. There is no preferred source or target office suite.

```text
LibreOffice ----┐                         ┌---- LibreOffice
ONLYOFFICE -----┤                         ├---- ONLYOFFICE
Microsoft Office├--> normalized OOXML --->├---- Microsoft Office
other OOXML ----┘                         └---- other OOXML
```

## Consumers

The thin JAR is reused directly by [`../quarkus`](../quarkus), so the Quarkus local service does not maintain a duplicate normalization implementation.

## Release naming

Java-related release files always contain `java` in their name. The core JAR is distinct from the Quarkus JAR and from the Java runtime-bundled portable packages:

```text
OOXML-Compat-Normalize-java-core.jar
OOXML-Compat-Normalize-java-quarkus.jar
OOXML-Compat-Normalize-java-portable-win-x64.zip
OOXML-Compat-Normalize-java-portable-linux-x64.tar.gz
```

## Licensing

The Java core source is MIT. Apache POI and docx4j are Apache License 2.0. The release JAR is shaded and contains transitive open-source dependencies; their upstream notices/licenses and the repository third-party notices must be retained when redistributing the JAR.
