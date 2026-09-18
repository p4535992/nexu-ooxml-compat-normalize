# OOXML Compat Normalize - Combined desktop portable

This portable distribution provides the same combined Java + Python web/API experience as the combined Docker image, without requiring Docker, Python, Java or .NET to be installed globally.

## Windows

Run:

```text
OOXML-Compat-Normalize-Combined.exe
```

The executable starts the local combined service and opens the default browser at:

```text
http://127.0.0.1:8080/ooxml-compat-normalize/
```

## Linux

Run:

```bash
./OOXML-Compat-Normalize-Combined
```

The executable starts the same local service and opens the default browser when a graphical browser is available.

## Engine modes

The combined desktop application supports the same runtime modes as the combined Docker image:

```text
both    Python + Java active (default)
python  only Python active
java    only Java / Quarkus active
```

The mode can be changed from the HTML page or through:

```text
GET  /ooxml-compat-normalize/api/mode
POST /ooxml-compat-normalize/api/mode?mode=both
POST /ooxml-compat-normalize/api/mode?mode=python
POST /ooxml-compat-normalize/api/mode?mode=java
```

Normal REST operations remain:

```text
GET  /ooxml-compat-normalize/api/info
POST /ooxml-compat-normalize/api/audit
POST /ooxml-compat-normalize/api/normalize?profile=interop-transitional-v1
```

When mode is `both`, add `engine=python` or `engine=java` to select the engine per operation.

## Portable layout

The distribution is intentionally a portable directory rather than a huge self-extracting single file:

```text
OOXML-Compat-Normalize-combined-portable-<os>-x64/
├── OOXML-Compat-Normalize-Combined[.exe]
├── runtime/                         bundled Java 17 runtime
├── java/
│   └── ooxml-compat-normalize-quarkus.jar
├── validator/
│   └── OpenXmlSdkValidator[.exe]
├── logs/
├── licenses/
│   └── dotnet/
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── THIRD_PARTY_LICENSES.md
└── README.md
```

The main launcher is a PyInstaller executable, not a Java launcher. It starts the bundled Java/Quarkus process only when the selected engine mode requires Java. The Python backend is executed from the same frozen application.

## Logs

Logs stay inside the extracted portable folder:

```text
logs/ooxml-compat-normalize-gateway.log
logs/ooxml-compat-normalize-python.log
logs/ooxml-compat-normalize-quarkus.log
```

## Configuration

Useful optional environment variables:

```text
OOXML_HTTP_PORT=8080
OOXML_CONTEXT_PATH=/ooxml-compat-normalize
OOXML_ENGINE_MODE=both|python|java
OOXML_DEFAULT_ENGINE=python|java
OOXML_OPEN_BROWSER=true|false
```

The desktop portable binds to `127.0.0.1` by default.

## Validation

The Python engine uses the bundled self-contained Microsoft Open XML SDK validator. The Java engine uses the bundled Quarkus service backed by Apache POI and docx4j.
