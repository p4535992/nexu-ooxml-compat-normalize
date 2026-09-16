from __future__ import annotations

import json
import logging
import os
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__
from .analysis import analyze_ooxml
from .normalizer import NormalizationOptions, normalize_ooxml
from .profile import PROFILE_BY_NAME
from .sdk_validator import validate_with_openxml_sdk


ALLOWED_EXTENSIONS = {".docx", ".xlsx", ".pptx"}
DEFAULT_PROFILE = "interop-transitional-v1"
MAX_BODY_SIZE = int(os.environ.get("OOXML_MAX_BODY_SIZE", str(256 * 1024 * 1024)))

INDEX_HTML = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OOXML Compat Normalize - Python</title>
  <style>
    body{font-family:system-ui,sans-serif;max-width:780px;margin:40px auto;padding:0 18px;line-height:1.45}
    fieldset{border:1px solid #bbb;border-radius:8px;padding:18px;margin:18px 0}
    button,select,input{font:inherit;padding:8px 10px;margin:4px}
    button{cursor:pointer}.muted{color:#666}.status{white-space:pre-wrap;background:#f5f5f5;padding:12px;border-radius:6px;min-height:44px}
  </style>
</head>
<body>
  <h1>OOXML Compat Normalize</h1>
  <p class="muted">Motore Python. Servizio HTTP/REST locale per DOCX, XLSX e PPTX.</p>

  <fieldset>
    <legend>Documento</legend>
    <input id="file" type="file" accept=".docx,.xlsx,.pptx">
    <select id="profile">
      <option value="interop-transitional-v1" selected>Interop consigliato</option>
      <option value="preserve-v1">Preserva</option>
      <option value="portable-explicit-v1">Portable esplicito</option>
    </select>
    <button id="audit" type="button">Analizza</button>
    <button id="normalize" type="button">Normalizza e scarica</button>
  </fieldset>

  <div id="status" class="status">Seleziona un file DOCX, XLSX o PPTX.</div>

  <script>
    const fileInput=document.getElementById('file');
    const status=document.getElementById('status');
    const profile=document.getElementById('profile');
    function selected(){const f=fileInput.files[0];if(!f)throw new Error('Seleziona un file.');return f;}
    async function post(path,file){
      const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':file.name},body:file});
      if(!r.ok)throw new Error((await r.text())||('HTTP '+r.status));
      return r;
    }
    document.getElementById('audit').addEventListener('click',async()=>{
      try{const f=selected();status.textContent='Analisi…';const r=await post('/api/audit',f);const j=await r.json();status.textContent=JSON.stringify(j,null,2);}catch(e){status.textContent='Errore: '+e.message;}
    });
    document.getElementById('normalize').addEventListener('click',async()=>{
      try{
        const f=selected();status.textContent='Normalizzazione…';
        const r=await post('/api/normalize?profile='+encodeURIComponent(profile.value),f);
        const blob=await r.blob();
        const cd=r.headers.get('Content-Disposition')||'';
        const m=/filename=\"([^\"]+)\"/.exec(cd);const name=m?m[1]:'normalized-'+f.name;
        const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
        status.textContent='Completato: '+name;
      }catch(e){status.textContent='Errore: '+e.message;}
    });
  </script>
</body>
</html>
"""


def _configure_logging() -> logging.Logger:
    logger = logging.getLogger("ooxml_compat_normalize.web")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    log_path = Path(os.environ.get("OOXML_LOG_FILE", "logs/ooxml-compat-normalize-python.log"))
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        rotating = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        rotating.setFormatter(formatter)
        logger.addHandler(rotating)
    except OSError as exc:
        logger.warning("File logging unavailable at %s: %s", log_path, exc)
    return logger


LOG = _configure_logging()


def _safe_filename(raw: str | None) -> str:
    if not raw or not raw.strip():
        raise ValueError("X-Filename header is required")
    safe = raw.replace("\\", "/").rsplit("/", 1)[-1].strip().replace('"', "_")
    suffix = Path(safe).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Only DOCX, XLSX and PPTX are supported")
    return safe


def _write_temp(body: bytes, filename: str) -> Path:
    if not body:
        raise ValueError("Empty file")
    handle = tempfile.NamedTemporaryFile(prefix="ooxml-python-input-", suffix=Path(filename).suffix, delete=False)
    try:
        handle.write(body)
        return Path(handle.name)
    finally:
        handle.close()


class OoxmlRequestHandler(BaseHTTPRequestHandler):
    server_version = "OOXMLCompatNormalizePython/1"

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info("HTTP %s - %s", self.address_string(), fmt % args)

    def _send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text: str, status: int) -> None:
        data = text.encode("utf-8", errors="replace")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> bytes:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Content-Length is required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length <= 0:
            raise ValueError("Empty file")
        if length > MAX_BODY_SIZE:
            raise OverflowError(f"Request body exceeds {MAX_BODY_SIZE} bytes")
        return self.rfile.read(length)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            data = INDEX_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/info":
            self._send_json(
                {
                    "name": "ooxml-compat-normalize-python",
                    "version": __version__,
                    "engine": "python",
                    "formats": ["docx", "xlsx", "pptx"],
                    "profiles": list(PROFILE_BY_NAME),
                }
            )
            return
        self._send_text("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            filename = _safe_filename(self.headers.get("X-Filename"))
            body = self._read_body()
            if parsed.path == "/api/audit":
                self._audit(filename, body)
                return
            if parsed.path == "/api/normalize":
                profile = parse_qs(parsed.query).get("profile", [DEFAULT_PROFILE])[0]
                self._normalize(filename, body, profile)
                return
            self._send_text("Not found", HTTPStatus.NOT_FOUND)
        except OverflowError as exc:
            LOG.warning("Request rejected: %s", exc)
            self._send_text(str(exc), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except (ValueError, FileNotFoundError) as exc:
            LOG.warning("Bad request: %s", exc)
            self._send_text(str(exc), HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # keep the local service alive and surface diagnostics
            LOG.exception("Request failed")
            self._send_text(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def _audit(self, filename: str, body: bytes) -> None:
        input_path = _write_temp(body, filename)
        try:
            LOG.info("Audit requested: file=%s bytes=%d", filename, len(body))
            analysis = analyze_ooxml(input_path).to_dict()
            sdk = validate_with_openxml_sdk(
                input_path,
                mode=os.environ.get("OOXML_SDK_VALIDATION", "auto"),
                max_errors=int(os.environ.get("OOXML_SDK_MAX_ERRORS", "200")),
            )
            payload = {
                "filename": filename,
                "engine": "python",
                "analysis": analysis,
                "openxml_sdk_validation": sdk,
            }
            LOG.info(
                "Audit completed: file=%s kind=%s parts=%s sdkAvailable=%s",
                filename,
                analysis.get("document_kind"),
                analysis.get("entry_count"),
                sdk.get("available"),
            )
            self._send_json(payload)
        finally:
            input_path.unlink(missing_ok=True)

    def _normalize(self, filename: str, body: bytes, profile_name: str) -> None:
        profile = PROFILE_BY_NAME.get(profile_name)
        if profile is None:
            raise ValueError(f"Unsupported profile: {profile_name}")
        input_path = _write_temp(body, filename)
        output_handle = tempfile.NamedTemporaryFile(
            prefix="ooxml-python-output-", suffix=Path(filename).suffix, delete=False
        )
        output_path = Path(output_handle.name)
        output_handle.close()
        try:
            LOG.info(
                "Normalization requested: file=%s bytes=%d profile=%s",
                filename,
                len(body),
                profile_name,
            )
            report = normalize_ooxml(
                input_path,
                output_path,
                options=NormalizationOptions(
                    profile=profile,
                    sdk_validation=os.environ.get("OOXML_SDK_VALIDATION", "auto"),
                    sdk_max_errors=int(os.environ.get("OOXML_SDK_MAX_ERRORS", "200")),
                ),
            )
            normalized = output_path.read_bytes()
            output_name = f"{Path(filename).stem}-normalized{Path(filename).suffix.lower()}"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{output_name}"')
            self.send_header("Content-Length", str(len(normalized)))
            self.send_header("X-OOXML-Engine", "python")
            self.send_header("X-OOXML-Kind", str(report.get("document_kind", "")))
            self.send_header("X-OOXML-Changed-Parts", str(report.get("changed_part_count", 0)))
            self.end_headers()
            self.wfile.write(normalized)
            LOG.info(
                "Normalization completed: file=%s kind=%s changedParts=%s outputBytes=%d",
                filename,
                report.get("document_kind"),
                report.get("changed_part_count"),
                len(normalized),
            )
        finally:
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)


def main() -> None:
    host = os.environ.get("OOXML_HTTP_HOST", "127.0.0.1")
    port = int(os.environ.get("OOXML_HTTP_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), OoxmlRequestHandler)
    LOG.info("OOXML Compat Normalize Python web service started on %s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        LOG.info("OOXML Compat Normalize Python web service stopped")


if __name__ == "__main__":
    main()
