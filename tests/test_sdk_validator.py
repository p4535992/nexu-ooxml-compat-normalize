from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from ooxml_compat_normalize.sdk_validator import SdkValidationError, validate_with_openxml_sdk


class OpenXmlSdkBridgeTests(unittest.TestCase):
    def test_auto_mode_parses_validator_json(self) -> None:
        payload = {
            "valid": True,
            "documentKind": "docx",
            "sdkVersion": "3.3.0",
            "fileFormatVersion": "Microsoft365",
            "errorCount": 0,
            "truncated": False,
            "errors": [],
        }
        completed = subprocess.CompletedProcess(
            args=["validator"], returncode=0, stdout=json.dumps(payload), stderr=""
        )
        with patch(
            "ooxml_compat_normalize.sdk_validator.find_openxml_sdk_validator",
            return_value=Path("/fake/OpenXmlSdkValidator"),
        ), patch("ooxml_compat_normalize.sdk_validator.subprocess.run", return_value=completed):
            result = validate_with_openxml_sdk("sample.docx")
        self.assertTrue(result["available"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["errorCount"], 0)

    def test_required_mode_fails_when_helper_missing(self) -> None:
        with patch(
            "ooxml_compat_normalize.sdk_validator.find_openxml_sdk_validator",
            return_value=None,
        ):
            with self.assertRaises(SdkValidationError):
                validate_with_openxml_sdk("sample.docx", mode="required")


if __name__ == "__main__":
    unittest.main()
