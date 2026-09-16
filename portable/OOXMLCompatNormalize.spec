# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os

root = Path.cwd().resolve()
validator = os.environ.get("OPENXML_VALIDATOR_BIN")
if not validator:
    raise SystemExit("OPENXML_VALIDATOR_BIN must point to the published OpenXmlSdkValidator binary")
validator_path = Path(validator).resolve()
if not validator_path.is_file():
    raise SystemExit(f"Open XML SDK validator not found: {validator_path}")

binaries = [(str(validator_path), "validator")]
datas = [
    (str(root / "LICENSE"), "."),
    (str(root / "THIRD_PARTY_NOTICES.md"), "."),
    (str(root / "THIRD_PARTY_LICENSES.md"), "."),
]

a = Analysis(
    [str(root / "portable" / "gui_entry.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
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
    name="OOXML-Compat-Normalize",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
