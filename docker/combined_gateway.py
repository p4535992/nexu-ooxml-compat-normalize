from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse
from urllib.request import Request, urlopen

DEFAULT_CONTEXT_PATH = "/ooxml-compat-normalize"
DEFAULT_ENGINE = os.environ.get("OOXML_DEFAULT_ENGINE", "python").strip().lower() or "python"
STARTUP_MODE = os.environ.get("OOXML_ENGINE_MODE", "both").strip().lower() or "both"
MAX_BODY_SIZE = int(os.environ.get("OOXML_MAX_BODY_SIZE", str(256 * 1024 * 1024)))
JAVA_PORT = int(os.environ.get("OOXML_JAVA_INTERNAL_PORT", "18081"))
PYTHON_PORT = int(os.environ.get("OOXML_PYTHON_INTERNAL_PORT", "18082"))
FROZEN = bool(getattr(sys, "frozen", False))
APP_ROOT = Path(
    os.environ.get(
        "OOXML_APP_ROOT",
        str(Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[1]),
    )
).resolve()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


_gateway_log_override = os.environ.get("OOXML_GATEWAY_LOG_FILE")
if _gateway_log_override:
    GATEWAY_LOG_FILE = Path(_gateway_log_override).resolve()
    LOG_DIR = Path(os.environ.get("OOXML_LOG_DIR", str(GATEWAY_LOG_FILE.parent))).resolve()
else:
    LOG_DIR = Path(os.environ.get("OOXML_LOG_DIR", str(APP_ROOT / "logs"))).resolve()
    GATEWAY_LOG_FILE = LOG_DIR / "ooxml-compat-normalize-gateway.log"

_java_candidate = APP_ROOT / "runtime" / "bin" / ("java.exe" if os.name == "nt" else "java")
JAVA_EXECUTABLE = os.environ.get("OOXML_JAVA_EXECUTABLE") or (str(_java_candidate) if _java_candidate.is_file() else "java")
QUARKUS_JAR = Path(
    os.environ.get("OOXML_QUARKUS_JAR", str(APP_ROOT / "java" / "ooxml-compat-normalize-quarkus.jar"))
).resolve()
VALIDATOR_EXECUTABLE = Path(
    os.environ.get(
        "OOXML_OPENXML_VALIDATOR",
        str(APP_ROOT / "validator" / ("OpenXmlSdkValidator.exe" if os.name == "nt" else "OpenXmlSdkValidator")),
    )
).resolve()
OPEN_BROWSER = _env_bool("OOXML_OPEN_BROWSER", FROZEN)
ENGINE_ORDER = ("python", "java")
ALLOWED_MODES = {"both", "python", "java"}


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
    raise SystemExit(f"OOXML_DEFAULT_ENGINE must be one of: {', '.join(ENGINE_ORDER)}")
if STARTUP_MODE not in ALLOWED_MODES:
    raise SystemExit("OOXML_ENGINE_MODE must be one of: both, python, java")

INDEX_HTML = """<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OOXML Compat Normalize - Java + Python</title>
  <style>
    body{font-family:system-ui,sans-serif;max-width:860px;margin:40px auto;padding:0 18px;line-height:1.45}
    fieldset{border:1px solid #bbb;border-radius:8px;padding:18px;margin:18px 0}
    button,select,input{font:inherit;padding:8px 10px;margin:4px}
    button{cursor:pointer}.muted{color:#666}.status{white-space:pre-wrap;background:#f5f5f5;padding:12px;border-radius:6px;min-height:44px}
    .engine-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.engine-info{font-size:.95em;color:#555}
  </style>
</head>
<body>
  <h1>OOXML Compat Normalize</h1>
  <p class="muted">Container combinato. Di default sono attivi Python + Java; puoi anche lasciare attivo un solo motore.</p>

  <fieldset>
    <legend>Modalità motori</legend>
    <div class="engine-row">
      <label for="mode">Modalità:</label>
      <select id="mode">
        <option value="both">Python + Java</option>
        <option value="python">Solo Python</option>
        <option value="java">Solo Java / Quarkus</option>
      </select>
      <button id="applyMode" type="button">Applica modalità</button>
      <span id="modeInfo" class="engine-info">Caricamento modalità…</span>
    </div>
  </fieldset>

  <fieldset>
    <legend>Motore per l'operazione</legend>
    <div class="engine-row">
      <label for="engine">Engine:</label>
      <select id="engine"></select>
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
    const mode=document.getElementById('mode');
    const modeInfo=document.getElementById('modeInfo');

    function selected(){const f=fileInput.files[0];if(!f)throw new Error('Seleziona un file.');return f;}
    function engineQuery(){return 'engine='+encodeURIComponent(engine.value);}

    function applyModeState(j){
      mode.value=j.mode;
      modeInfo.textContent='Attivi: '+j.enabledEngines.join(' + ');
      const old=engine.value;
      engine.innerHTML='';
      for(const value of j.enabledEngines){
        const option=document.createElement('option');
        option.value=value;
        option.textContent=value==='java'?'Java / Quarkus':'Python';
        engine.appendChild(option);
      }
      if(j.enabledEngines.includes(old))engine.value=old;
      else if(j.enabledEngines.includes(j.defaultEngine))engine.value=j.defaultEngine;
      else engine.value=j.enabledEngines[0];
      engine.disabled=j.enabledEngines.length===1;
    }

    async function loadMode(){
      const r=await fetch('api/mode');
      if(!r.ok)throw new Error((await r.text())||('HTTP '+r.status));
      const j=await r.json();
      applyModeState(j);
      await refreshInfo();
    }

    async function refreshInfo(){
      if(!engine.value){engineInfo.textContent='Nessun motore disponibile';return;}
      try{
        const r=await fetch('api/info?'+engineQuery());
        if(!r.ok)throw new Error((await r.text())||('HTTP '+r.status));
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

    document.getElementById('applyMode').addEventListener('click',async()=>{
      const button=document.getElementById('applyMode');
      try{
        button.disabled=true;status.textContent='Cambio modalità motori…';
        const r=await fetch('api/mode?mode='+encodeURIComponent(mode.value),{method:'POST'});
        if(!r.ok)throw new Error((await r.text())||('HTTP '+r.status));
        const j=await r.json();applyModeState(j);await refreshInfo();
        status.textContent='Modalità applicata: '+j.mode+'.';
      }catch(e){status.textContent='Errore cambio modalità: '+e.message;await loadMode().catch(()=>{});}
      finally{button.disabled=false;}
    });

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

    loadMode().catch(e=>{status.textContent='Errore inizializzazione: '+e.message;});
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
    log_path = GATEWAY_LOG_FILE
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


def backend_environment(engine: str) -> dict[str, str]:
    env = os.environ.copy()
    if engine == "java":
        env.update(
            {
                "QUARKUS_HTTP_HOST": "127.0.0.1",
                "QUARKUS_HTTP_PORT": str(JAVA_PORT),
                "OOXML_CONTEXT_PATH": CONTEXT_PATH,
                "OOXML_LOG_FILE": str(LOG_DIR / "ooxml-compat-normalize-quarkus.log"),
                "OOXML_OPEN_BROWSER": "false",
            }
        )
    else:
        env.update(
            {
                "OOXML_HTTP_HOST": "127.0.0.1",
                "OOXML_HTTP_PORT": str(PYTHON_PORT),
                "OOXML_CONTEXT_PATH": CONTEXT_PATH,
                "OOXML_LOG_FILE": str(LOG_DIR / "ooxml-compat-normalize-python.log"),
                "OOXML_OPENXML_VALIDATOR": str(VALIDATOR_EXECUTABLE),
                "OOXML_SDK_VALIDATION": "required",
            }
        )
    return env


def launch_backend(engine: str) -> subprocess.Popen[bytes]:
    if engine == "java":
        if not QUARKUS_JAR.is_file():
            raise RuntimeError(f"Quarkus JAR not found: {QUARKUS_JAR}")
        command = [JAVA_EXECUTABLE, "-jar", str(QUARKUS_JAR)]
    elif FROZEN:
        command = [sys.executable, "--python-backend"]
    else:
        command = [sys.executable, "-m", "ooxml_compat_normalize.web_server"]

    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(command, env=backend_environment(engine), **kwargs)
    try:
        wait_for_backend(engine, process)
    except Exception:
        stop_process(process)
        raise
    return process


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass


def desired_engines(mode: str) -> tuple[str, ...]:
    if mode == "both":
        return ENGINE_ORDER
    return (mode,)


class EngineManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._mode = STARTUP_MODE

    def mode(self) -> str:
        with self._lock:
            return self._mode

    def enabled_engines(self) -> list[str]:
        with self._lock:
            return [engine for engine in ENGINE_ORDER if engine in self._processes]

    def default_engine(self) -> str:
        enabled = self.enabled_engines()
        if DEFAULT_ENGINE in enabled:
            return DEFAULT_ENGINE
        if enabled:
            return enabled[0]
        return DEFAULT_ENGINE

    def is_enabled(self, engine: str) -> bool:
        with self._lock:
            process = self._processes.get(engine)
            return process is not None and process.poll() is None

    def set_mode(self, mode: str) -> None:
        mode = mode.strip().lower()
        if mode not in ALLOWED_MODES:
            raise ValueError("mode must be 'both', 'python' or 'java'")
        wanted = desired_engines(mode)
        with self._lock:
            for engine in wanted:
                process = self._processes.get(engine)
                if process is None or process.poll() is not None:
                    if process is not None:
                        self._processes.pop(engine, None)
                    LOG.info("Starting %s backend for mode=%s", engine, mode)
                    self._processes[engine] = launch_backend(engine)

            for engine in list(self._processes):
                if engine not in wanted:
                    process = self._processes.pop(engine)
                    LOG.info("Stopping %s backend for mode=%s", engine, mode)
                    stop_process(process)

            self._mode = mode
            LOG.info("Engine mode active: mode=%s enabled=%s", mode, ",".join(self.enabled_engines()))

    def state(self) -> dict[str, object]:
        return {
            "mode": self.mode(),
            "enabledEngines": self.enabled_engines(),
            "defaultEngine": self.default_engine(),
        }

    def processes_snapshot(self) -> dict[str, subprocess.Popen[bytes]]:
        with self._lock:
            return dict(self._processes)

    def stop_all(self) -> None:
        with self._lock:
            processes = list(self._processes.values())
            self._processes.clear()
        for process in processes:
            stop_process(process)


MANAGER = EngineManager()


class EngineDisabledError(ValueError):
    pass


class CombinedHandler(BaseHTTPRequestHandler):
    server_version = "OOXMLCompatNormalizeCombined/2"

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
        engine = query_engine or header_engine or MANAGER.default_engine()
        if engine not in BACKENDS:
            raise ValueError("engine must be 'java' or 'python'")
        if not MANAGER.is_enabled(engine):
            raise EngineDisabledError(f"engine '{engine}' is disabled in mode '{MANAGER.mode()}'")
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
                forwarded["X-OOXML-Engine-Mode"] = MANAGER.mode()
                self.send_bytes(response.status, payload, forwarded)
        except HTTPError as exc:
            payload = exc.read()
            forwarded = {"Content-Type": exc.headers.get("Content-Type", "text/plain; charset=utf-8")}
            forwarded["X-OOXML-Selected-Engine"] = engine
            forwarded["X-OOXML-Engine-Mode"] = MANAGER.mode()
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
            self.send_json({"status": "ok", "engine": "combined", "contextPath": CONTEXT_PATH, **MANAGER.state()})
            return
        if parsed.path == API_BASE + "/mode":
            self.send_json({"engine": "combined", "contextPath": CONTEXT_PATH, **MANAGER.state()})
            return
        if parsed.path == API_BASE + "/info":
            try:
                query_engine = parse_qs(parsed.query).get("engine", [""])[0].strip().lower()
                if query_engine:
                    engine = self.selected_engine(parsed)
                    self.proxy(engine, "GET", parsed)
                    return
                infos = {engine: backend_info(engine) for engine in MANAGER.enabled_engines()}
                self.send_json(
                    {
                        "name": "ooxml-compat-normalize-combined",
                        "engine": "combined",
                        "contextPath": CONTEXT_PATH,
                        **MANAGER.state(),
                        "engines": infos,
                        "formats": ["docx", "xlsx", "pptx"],
                        "profiles": ["preserve-v1", "interop-transitional-v1", "portable-explicit-v1"],
                    }
                )
            except EngineDisabledError as exc:
                self.send_text(str(exc), HTTPStatus.CONFLICT)
            except (ValueError, OSError, URLError, HTTPError) as exc:
                LOG.exception("Combined info request failed")
                self.send_text(str(exc), HTTPStatus.BAD_GATEWAY)
            return
        self.send_text("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == API_BASE + "/mode":
            try:
                mode = parse_qs(parsed.query).get("mode", [""])[0].strip().lower()
                if not mode:
                    raise ValueError("mode query parameter is required: both, python or java")
                MANAGER.set_mode(mode)
                self.send_json({"engine": "combined", "contextPath": CONTEXT_PATH, **MANAGER.state()})
            except ValueError as exc:
                self.send_text(str(exc), HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                LOG.exception("Engine mode change failed")
                self.send_text(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if parsed.path not in {API_BASE + "/audit", API_BASE + "/normalize"}:
            self.send_text("Not found", HTTPStatus.NOT_FOUND)
            return
        try:
            engine = self.selected_engine(parsed)
            body = self.read_body()
            LOG.info(
                "Proxy request: mode=%s engine=%s endpoint=%s file=%s bytes=%d",
                MANAGER.mode(),
                engine,
                parsed.path,
                self.headers.get("X-Filename", ""),
                len(body),
            )
            self.proxy(engine, "POST", parsed, body)
        except OverflowError as exc:
            self.send_text(str(exc), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        except EngineDisabledError as exc:
            self.send_text(str(exc), HTTPStatus.CONFLICT)
        except ValueError as exc:
            self.send_text(str(exc), HTTPStatus.BAD_REQUEST)


def _open_browser(port: int) -> None:
    if not OPEN_BROWSER:
        return
    url = f"http://127.0.0.1:{port}{UI_PATH}"

    def opener() -> None:
        time.sleep(0.5)
        try:
            webbrowser.open(url, new=2)
            LOG.info("Opened default browser: %s", url)
        except Exception:
            LOG.exception("Could not open default browser: %s", url)

    threading.Thread(target=opener, name="ooxml-browser-opener", daemon=True).start()


def _run_frozen_python_backend() -> None:
    from ooxml_compat_normalize.web_server import main as python_web_main

    python_web_main()


def main() -> None:
    host = os.environ.get("OOXML_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("OOXML_HTTP_PORT", "8080"))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    MANAGER.set_mode(STARTUP_MODE)
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
            for engine, process in MANAGER.processes_snapshot().items():
                if process.poll() is not None:
                    LOG.error("%s backend exited unexpectedly with code %s", engine, process.returncode)
                    stopping.set()
                    server.shutdown()
                    return

    threading.Thread(target=monitor_children, daemon=True).start()
    LOG.info(
        "OOXML Compat Normalize combined gateway started on %s:%d%s/ mode=%s defaultEngine=%s enabled=%s",
        host,
        port,
        CONTEXT_PATH,
        MANAGER.mode(),
        MANAGER.default_engine(),
        ",".join(MANAGER.enabled_engines()),
    )
    _open_browser(port)
    try:
        server.serve_forever()
    finally:
        stopping.set()
        server.server_close()
        MANAGER.stop_all()
        LOG.info("OOXML Compat Normalize combined gateway stopped")


if __name__ == "__main__":
    if FROZEN and "--python-backend" in sys.argv[1:]:
        _run_frozen_python_backend()
    else:
        main()
