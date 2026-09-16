#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RID="${RID:-linux-x64}"
VALIDATOR_PROJECT="$ROOT/dotnet/OpenXmlSdkValidator/OpenXmlSdkValidator.csproj"

echo "Publishing self-contained Open XML SDK validator for $RID..."
dotnet publish "$VALIDATOR_PROJECT" \
  -c Release \
  -r "$RID" \
  --self-contained true \
  -p:PublishSingleFile=true \
  -p:IncludeNativeLibrariesForSelfExtract=true \
  -p:DebugType=None \
  -p:DebugSymbols=false

VALIDATOR="$ROOT/dotnet/OpenXmlSdkValidator/bin/Release/net8.0/$RID/publish/OpenXmlSdkValidator"
if [[ ! -f "$VALIDATOR" ]]; then
  echo "Validator build not found: $VALIDATOR" >&2
  exit 2
fi

VENV="$ROOT/.build-venv"
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
PYTHON="$VENV/bin/python"
PYINSTALLER="$VENV/bin/pyinstaller"

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -e '.[portable]'

export OPENXML_VALIDATOR_BIN="$VALIDATOR"
"$PYINSTALLER" --clean --noconfirm "$ROOT/portable/OOXMLCompatNormalize.spec"
chmod +x "$ROOT/dist/OOXML-Compat-Normalize"

echo
echo "Portable executable created:"
echo "$ROOT/dist/OOXML-Compat-Normalize"
