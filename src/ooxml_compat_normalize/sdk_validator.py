from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


class SdkValidationError(RuntimeError):
    pass


def _candidate_paths() -> list[Path]:
    candidates: list[Path] = []

    explicit = os.environ.get("OOXML_OPENXML_VALIDATOR")
    if explicit:
        candidates.append(Path(explicit))

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass) / "validator"
        candidates.extend((base / "OpenXmlSdkValidator.exe", base / "OpenXmlSdkValidator"))

    package_root = Path(__file__).resolve().parents[2]
    for rid in ("win-x64", "win-arm64", "linux-x64", "linux-arm64"):
        publish = package_root / "dotnet" / "OpenXmlSdkValidator" / "bin" / "Release" / "net8.0" / rid / "publish"
        candidates.extend((publish / "OpenXmlSdkValidator.exe", publish / "OpenXmlSdkValidator"))

    for command in ("OpenXmlSdkValidator", "OpenXmlSdkValidator.exe"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(Path(resolved))

    return candidates


def find_openxml_sdk_validator() -> Path | None:
    for candidate in _candidate_paths():
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def validate_with_openxml_sdk(
    path: str | Path,
    *,
    mode: str = "auto",
    max_errors: int = 200,
) -> dict:
    """Validate an OOXML file with the bundled Open XML SDK helper.

    mode:
      - ``off``: skip validation;
      - ``auto``: validate when the helper is available, otherwise report unavailable;
      - ``required``: helper absence or execution failure is fatal.
    """
    if mode not in {"off", "auto", "required"}:
        raise ValueError(f"Unsupported SDK validation mode: {mode}")

    if mode == "off":
        return {"enabled": False, "available": False, "skipped": True, "reason": "disabled"}

    helper = find_openxml_sdk_validator()
    if helper is None:
        result = {
            "enabled": True,
            "available": False,
            "skipped": True,
            "reason": "OpenXmlSdkValidator helper not found",
        }
        if mode == "required":
            raise SdkValidationError(result["reason"])
        return result

    target = Path(path)
    try:
        completed = subprocess.run(
            [str(helper), str(target), "--max-errors", str(max_errors)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        if mode == "required":
            raise SdkValidationError(f"Open XML SDK validator could not be executed: {exc}") from exc
        return {
            "enabled": True,
            "available": True,
            "skipped": True,
            "reason": f"validator execution failed: {exc}",
            "helper": str(helper),
        }

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        message = (
            "Open XML SDK validator returned non-JSON output"
            + (f": {completed.stderr.strip()}" if completed.stderr.strip() else "")
        )
        if mode == "required":
            raise SdkValidationError(message) from exc
        return {
            "enabled": True,
            "available": True,
            "skipped": True,
            "reason": message,
            "helper": str(helper),
            "return_code": completed.returncode,
        }

    payload["enabled"] = True
    payload["available"] = True
    payload["skipped"] = False
    payload["helper"] = str(helper)
    payload["return_code"] = completed.returncode

    operational_error = bool(payload.get("operationalError")) or completed.returncode == 2
    if operational_error and mode == "required":
        raise SdkValidationError(payload.get("message") or "Open XML SDK validation failed operationally")

    return payload
