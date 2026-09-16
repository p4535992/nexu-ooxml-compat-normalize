# Portable GUI builds

The portable application combines two components into a **single end-user executable**:

1. the conservative Python OOXML normalization engine and Tkinter GUI;
2. a self-contained .NET 8 helper using **Microsoft Open XML SDK** for independent structural validation before and after normalization.

PyInstaller embeds the self-contained validator binary inside the one-file application. At runtime it is extracted to the application's temporary bundle directory and invoked locally; the user does not need Python, .NET, LibreOffice, ONLYOFFICE or Microsoft Office installed.

## Windows x64

Requirements on the **build machine only**:

- Python 3.10+;
- .NET 8 SDK.

Build:

```powershell
.\portable\build_windows_portable.ps1
```

Output:

```text
dist\OOXML-Compat-Normalize.exe
```

## Linux x64

Requirements on the **build machine only**:

- Python 3.10+ with Tk development/runtime support;
- .NET 8 SDK;
- a C toolchain compatible with PyInstaller's bootloader already distributed through the PyInstaller wheel.

Build:

```bash
./portable/build_linux_portable.sh
```

Output:

```text
dist/OOXML-Compat-Normalize
```

The Linux executable is self-contained with respect to Python and .NET, but a graphical desktop still provides normal OS libraries used by Tk/X11/Wayland/fontconfig.

## GitHub Actions

`.github/workflows/portable-release.yml` builds Windows x64 and Linux x64 portable artifacts. A tag matching `v*` triggers a GitHub Release. A manual workflow run can also create a release and tag by setting `release_tag` (for example `v0.4.0`).

Each release contains platform archives and SHA-256 checksums.
