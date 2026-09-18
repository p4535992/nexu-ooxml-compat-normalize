# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

root = Path.cwd().resolve()

a = Analysis(
    [str(root / "docker" / "combined_gateway.py")],
    pathex=[str(root / "src"), str(root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "ooxml_compat_normalize.web_server",
        "ooxml_compat_normalize.analysis",
        "ooxml_compat_normalize.normalizer",
        "ooxml_compat_normalize.profile",
        "ooxml_compat_normalize.sdk_validator",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="OOXML-Compat-Normalize-Combined",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=(sys.platform != "win32"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
