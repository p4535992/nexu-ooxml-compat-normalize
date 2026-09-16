# Third-party license summary

This file is a distribution-oriented summary. The authoritative license shipped by each exact dependency version controls.

## Microsoft Open XML SDK (`DocumentFormat.OpenXml`)

License: MIT.

Copyright (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## .NET runtime

License: MIT for the .NET runtime project, together with third-party notices applicable to the exact runtime build included by `dotnet publish --self-contained`.

## Python

License: Python Software Foundation License. Portable builds include a CPython runtime through the bundler.

## Tcl/Tk

License: permissive Tcl/Tk license terms. Tkinter-based portable builds may include Tcl/Tk runtime components required by the GUI.

## PyInstaller bootloader

License: GPLv2 with the PyInstaller bootloader exception permitting distribution of bundled applications under the application's own license, subject to the authoritative upstream terms for the exact PyInstaller release used to build the binary.

## Apache POI 5.5.1

License: Apache License, Version 2.0.

Purpose in this project: Java-side OPC/OOXML parsing and cross-format validation for DOCX, XLSX and PPTX.

Upstream: https://poi.apache.org/

## docx4j 17.1.0

License: Apache License, Version 2.0.

Purpose in this project: second independent Java OOXML package/model parser used by the standalone JAR for pre-flight/post-flight validation.

Upstream: https://www.docx4java.org/

The shaded Java JAR also contains Maven-resolved transitive dependencies under their own open-source terms. Upstream `META-INF` license/notice resources and the Java module `THIRD-PARTY-NOTICES.txt` resource are part of the distribution inputs.
