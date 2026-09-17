from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse
from urllib.request import Request, urlopen

DEFAULT_CONTEXT_PATH = "/ooxml-compat-normalize"
DEFAULT_ENGINE = os.environ.get("OOXML_DEFAULT_ENGINE", "python").strip().lower() or "python"
MAX_BODY_SIZE = int(os.environ.get("OOXML_MAX_BODY_SIZE", str(256 * 1024 * 1024)))
JAVA_PORT = int(os.environ.get("OOXML_JAVA_INTERNAL_PORT", "18081"))
PYTHON_PORT = int(os.environ.get("OOXML_PYTHON_INTERNAL_PORT", "18082"))


def normalize_context_path(raw: str | None) -> str:
    value = (raw or DEFAULT_CONTEXT_PATH).strip()
    if not value or value == "/":
        value = DEFAULT_CONTEXT_PATH
    if not value.startswith("/"):
        value = "/" + value
    value = "/" + "/".join(segment for segment in value.split("/") if segment)
    return value.rstrip("/")


CONTEXT_PATH = normalize_context_path(os.environ.get("OOXML_CONTEXT_PATH"))
UI_PATH = CONTEXT_PATH + "/"
API_BASE = CONTEXT_PATH + "/api"
BACKENDS = {
    "java": f"http://127.0.0.1:{JAVA_PORT}{CONTEXT_PATH}",
    "python": f"http://127.0.0.1:{PYTHON_PORT}{CONTEXT_PATH}",
}

if DEFAULT_ENGINE not in BACKENDS:
    raise SystemExit(f"OOXML_DEFAULT_ENGINE must be one of: {', '.join(BACKENDS)}")

INDEX_HTML = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OOXML Compat Normalize - Java + Python</title>
  <style>
    body{font-family:system-ui,sans-serif;max-width:820px;margin:40px auto;padding:0 18px;line-height:1.45}
    fieldset{border:1px solid #bbb;border-radius:8px;padding:18px;margin:18px 0}
    button,select,input{font:inherit;padding:8px 10px;margin:4px}
    button{cursor:pointer}.muted{color:#666}.status{white-space:pre-wrap;background:#f5f5f5;padding:12px;border-radius:6px;min-height:44px}
    .engine-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.engine-info{font-size:.95em;color:#555}
  </style>
</head>
<body>
  <h1>OOXML Compat Normalize</h1>
  <p class="muted">Container combinato. Scegli il motore Java/Quarkus oppure Python prima di analizzare o normalizzare il documento.</p>

  <fieldset>
    <legend>Motore</legend>
    <div class="engine-row">
      <label for="engine">Engine:</label>
      <select id="engine">
        <option value="python">Python</option>
        <option value="java">Java / Quarkus</option>
      </select>
      <span id="engineInfo" class="engine-info">Caricamento informazioni…</span>
    </div>
  </fieldset>

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
    const engine=document.getElementById('engine');
    const engineInfo=document.getElementById('engineInfo');

    function selected(){const f=fileInput.files[0];if(!f)throw new Error('Seleziona un file.');return f;}
    function engineQuery(){return 'engine='+encodeURIComponent(engine.value);}

    async function refreshInfo(){
      try{
        const r=await fetch('api/info?'+engineQuery());
        if(!r.ok)throw new Error('HTTP '+r.status);
        const j=await r.json();
        engineInfo.textContent=(j.name||engine.value)+' · '+(j.version||'versione n/d');
      }catch(e){engineInfo.textContent='Motore non disponibile: '+e.message;}
    }

    async function post(path,file){
      const sep=path.includes('?')?'&':'?';
      const r=await fetch(path+sep+engineQuery(),{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Filename':file.name,'X-OOXML-Engine':engine.value},body:file});
      if(!r.ok)throw new Error((await r.text())||('HTTP '+r.status));
      return r;
    }

    engine.addEventListener('change',refreshInfo);

    document.getElementById('audit').addEventListener('click',async()=>{
      try{
        const f=selected();status.textContent='Analisi con '+engine.value+'…';
        const r=await post('api/audit',f);const j=await r.json();
        status.textContent=JSON.stringify(j,null,2);
      }catch(e){status.textContent='Errore: '+e.message;}
    });

    document.getElementById('normalize').addEventListener('click',async()=>{
      try{
        const f=selected();status.textContent='Normalizzazione con '+engine.value+'…';
        const r=await post('api/normalize?profile='+encodeURIComponent(profile.value),f);
        const blob=await r.blob();
        const cd=r.headers.get('Content-Disposition')||'';
        const m=/filename=\"([^\"]+)\"/.exec(cd);const name=m?m[1]:'normalized-'+f.name;
        const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
        status.textContent='Completato con '+engine.value+': '+name;
      }catch(e){status.textContent='Errore: '+e.message;}
    });

    fetch('api/info').then(r=>r.ok?r.json():Promise.reject(new Error('HTTP '+r.status))).then(j=>{
      if(j.defaultEngine && ['java','python'].includes(j.defaultEngine))engine.value=j.defaultEngine;
      return refreshInfo();
    }).catch(()=>refreshInfo());
  </script>
</body>
</html>
"""


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("ooxml_combined_gateway")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    log_path = Path(os.environ.get("OOXML_GATEWAY_LOG_FILE", "/data/logs/ooxml-compat-normalize-gateway.log"))
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        rotating = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        rotating.setFormatter(formatter)
        logger.addHandler(rotating)
    except OSError as exc:
        logger.warning("Gateway file logging unavailable at %s: %s", log_path, exc)
    return logger


LOG = configure_logging()


def backend_info(engine: str) -> dict[str, object]:
    with urlopen(BACKENDS[engine] + "/api/info", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_backend(engine: str, process: subprocess.Popen[bytes], timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{engine} backend exited with code {process.returncode}")
        try:
            info = backend_info(engine)
            LOG.info("%s backend ready: %s", engine, info.get("version", "unknown"))
            return
        except (OSError, ValueError, URLError, HTTPError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"{engine} backend did not become ready: {last_error}")


def start_backends() -> dict[str, subprocess.Popen[bytes]]:
    java_env = os.environ.copy()
    java_env.update(
        {
            "QUARKUS_HTTP_HOST": "127.0.0.1",
            "QUARKUS_HTTP_PORT": str(JAVA_PORT),
            "OOXML_CONTEXT_PATH": CONTEXT_PATH,
            "OOXML_LOG_FILE": "/data/logs/ooxml-compat-normalize-quarkus.log",
            "OOXML_OPEN_BROWSER": "false",
        }
    )
    python_env = os.environ.copy()
    python_env.update(
        {
            "OOXML_HTTP_HOST": "127.0.0.1",
            "OOXML_HTTP_PORT": str(PYTHON_PORT),
            "OOXML_CONTEXT_PATH": CONTEXT_PATH,
            "OOXML_LOG_FILE": "/data/logs/ooxml-compat-normalize-python.log",
            "OOXML_OPENXML_VALIDATOR": "/app/validator/OpenXmlSdkValidator",
            "OOXML_SDK_VALIDATION": "required",
        }
    )

    processes = {
        "java": subprocess.Popen(
            ["java", "-jar", "/app/java/ooxml-compat-normalize-quarkus.jar"],
            env=java_env,
        ),
        "python": subprocess.Popen(
            [sys.executable, "-m", "ooxml_compat_normalize.web_server"],
            env=python_env,
        ),
    }
    try:
        for engine, process in processes.items():
            wait_for_backend(engine, process)
    except Exception:
        stop_backends(processes)
        raise
    return processes


def stop_backends(processes: dict[str, subprocess.Popen[bytes]]) -> None:
    for process in processes.values():
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 8
    for process in processes.values():
        remaining = max(0.0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
    for process in processes.values():
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


class CombinedHandler(BaseHTTPRequestHandler):
    server_version = "OOXMLCompatNormalizeCombined/1"

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info("HTTP %s - %s", self.address_string(), fmt % args)

    def send_bytes(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        supplied = {k.lower() for k in (headers or {})}
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        if "content-length" not in supplied:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_bytes(status, body, {"Content-Type": "application/json; charset=utf-8"})

    def send_text(self, text: str, status: int) -> None:
        self.send_bytes(status, text.encode("utf-8", errors="replace"), {"Content-Type": "text/plain; charset=utf-8"})

    def redirect(self, location: str) -> None:
        self.send_bytes(HTTPStatus.TEMPORARY_REDIRECT, b"", {"Location": location})

    def selected_engine(self, parsed) -> str:
        query_engine = parse_qs(parsed.query).get("engine", [""])[0].strip().lower()
        header_engine = (self.headers.get("X-OOXML-Engine") or "").strip().lower()
        engine = query_engine or header_engine or DEFAULT_ENGINE
        if engine not in BACKENDS:
            raise ValueError("engine must be 'java' or 'python'")
        return engine

    def read_body(self) -> bytes:
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

    def proxy(self, engine: str, method: str, parsed, body: bytes | None = None) -> None:
        pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "engine"]
        query = urlencode(pairs, doseq=True)
        suffix = parsed.path[len(CONTEXT_PATH):]
        target = BACKENDS[engine] + suffix + (("?" + query) if query else "")
        headers = {"Accept": self.headers.get("Accept", "*/*")}
        if body is not None:
            headers["Content-Type"] = self.headers.get("Content-Type", "application/octet-stream")
            filename = self.headers.get("X-Filename")
            if filename:
                headers["X-Filename"] = filename
        request = Request(target, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=300) as response:
                payload = response.read()
                forwarded: dict[str, str] = {}
                for key in ("Content-Type", "Content-Disposition", "X-OOXML-Engine", "X-OOXML-Kind", "X-OOXML-Changed-Parts"):
                    value = response.headers.get(key)
                    if value:
                        forwarded[key] = value
                forwarded["X-OOXML-Selected-Engine"] = engine
                self.send_bytes(response.status, payload, forwarded)
        except HTTPError as exc:
            payload = exc.read()
            forwarded = {"Content-Type": exc.headers.get("Content-Type", "text/plain; charset=utf-8")}
            forwarded["X-OOXML-Selected-Engine"] = engine
            self.send_bytes(exc.code, payload, forwarded)
        except URLError as exc:
            LOG.error("Backend unavailable: engine=%s target=%s error=%s", engine, target, exc)
            self.send_text(f"{engine} backend unavailable", HTTPStatus.BAD_GATEWAY)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == CONTEXT_PATH:
            self.redirect(UI_PATH)
            return
        if parsed.path == UI_PATH:
            self.send_bytes(HTTPStatus.OK, INDEX_HTML.encode("utf-8"), {"Content-Type": "text/html; charset=utf-8"})
            return
        if parsed.path == API_BASE + "/health":
            self.send_json({"status": "ok", "engine": "combined", "contextPath": CONTEXT_PATH})
            return
        if parsed.path == API_BASE + "/info":
            try:
                query_engine = parse_qs(parsed.query).get("engine", [""])[0].strip().lower()
                if query_engine:
                    engine = self.selected_engine(parsed)
                    self.proxy(engine, "GET", parsed)
                    return
                infos = {engine: backend_info(engine) for engine in BACKENDS}
                self.send_json(
                    {
                        "name": "ooxml-compat-normalize-combined",
                        "engine": "combined",
                        "defaultEngine": DEFAULT_ENGINE,
                        "contextPath": CONTEXT_PATH,
                        "engines": infos,
                        "formats": ["docx", "xlsx", "pptx"],
                        "profiles": ["preserve-v1", "interop-transitional-v1", "portable-explicit-v1"],
                    }
                )
            except (ValueError, OSError, URLError, HTTPError) as exc:
                LOG.exception("Combined info request failed")
                self.send_text(str(exc), HTTPStatus.BAD_GATEWAY)
            return
        self.send_text("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in {API_BASE + "/audit", API_BASE + "/normalize"}:
            self.send_text("Not found", HTTPStatus.NOT_FOUND)
            return
        try:
            engine = self.selected_engine(parsed)
            body = self.read_body()
            LOG.info(
                "Proxy request: engine=%s endpoint=%s file=%s bytes=%d",
                engine,
                parsed.path,
                self.headers.get("X-Filename", ""),
                len(body),
            )
            self.proxy(engine, "POST", parsed, body)
        except OverflowError as exc:
            self.send_text(str(exc), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except ValueError as exc:
            self.send_text(str(exc), HTTPStatus.BAD_REQUEST)


def main() -> None:
    host = os.environ.get("OOXML_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("OOXML_HTTP_PORT", "8080"))
    processes = start_backends()
    server = ThreadingHTTPServer((host, port), CombinedHandler)
    stopping = threading.Event()

    def shutdown_from_signal(signum: int, _frame) -> None:
        if stopping.is_set():
            return
        stopping.set()
        LOG.info("Shutdown requested by signal %s", signum)
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown_from_signal)
    signal.signal(signal.SIGINT, shutdown_from_signal)

    def monitor_children() -> None:
        while not stopping.wait(1.0):
            for engine, process in processes.items():
                if process.poll() is not None:
                    LOG.error("%s backend exited unexpectedly with code %s", engine, process.returncode)
                    stopping.set()
                    server.shutdown()
                    return

    threading.Thread(target=monitor_children, daemon=True).start()
    LOG.info(
        "OOXML Compat Normalize combined gateway started on %s:%d%s/ defaultEngine=%s",
        host,
        port,
        CONTEXT_PATH,
        DEFAULT_ENGINE,
    )
    try:
        server.serve_forever()
    finally:
        stopping.set()
        server.server_close()
        stop_backends(processes)
        LOG.info("OOXML Compat Normalize combined gateway stopped")


if __name__ == "__main__":
    main()
