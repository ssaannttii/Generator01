#!/usr/bin/env python3
"""Lightweight HTML interface for the star chart generator."""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import sys
import threading
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Make the ``src`` package importable when running from a checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from star_chart_generator import SceneConfig, generate_star_chart  # noqa: E402


DEFAULT_CONFIG_DIR = PROJECT_ROOT / "configs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


INDEX_HTML = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Star Chart Generator</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: 'Segoe UI', Roboto, system-ui, sans-serif;
    }
    body {
      margin: 0;
      background: #070b16;
      color: #f1f5ff;
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 64px;
      box-sizing: border-box;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 24px;
    }
    h1 {
      font-size: 2rem;
      margin: 0;
    }
    h2 {
      font-size: 1.25rem;
      margin-top: 0;
    }
    section {
      background: rgba(17, 24, 39, 0.75);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 28px;
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
    }
    label {
      display: block;
      margin-bottom: 12px;
      font-weight: 600;
    }
    select, input[type=\"number\"], textarea {
      width: 100%;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid rgba(148, 163, 184, 0.5);
      background: rgba(15, 23, 42, 0.95);
      color: inherit;
      font-size: 1rem;
      box-sizing: border-box;
      margin-top: 6px;
    }
    textarea {
      min-height: 140px;
      font-family: 'Fira Code', 'JetBrains Mono', monospace;
      resize: vertical;
    }
    button {
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      border: none;
      color: white;
      padding: 10px 18px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 1rem;
      cursor: pointer;
      transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    button:hover:not([disabled]) {
      transform: translateY(-1px);
      box-shadow: 0 12px 22px rgba(99, 102, 241, 0.35);
    }
    button[disabled] {
      opacity: 0.6;
      cursor: wait;
      box-shadow: none;
    }
    .row {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }
    .row > * {
      flex: 1 1 220px;
    }
    .checkbox {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
    }
    .checkbox input {
      width: auto;
    }
    #render-status {
      min-height: 1.5em;
      margin-top: 12px;
      font-weight: 500;
    }
    #render-result {
      margin-top: 18px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    #render-result img {
      max-width: 100%;
      border-radius: 12px;
      border: 1px solid rgba(148, 163, 184, 0.35);
      box-shadow: 0 18px 36px rgba(15, 23, 42, 0.6);
      background: black;
    }
    .subtle {
      color: rgba(226, 232, 240, 0.76);
      font-size: 0.95rem;
    }
    .console-output h3 {
      margin-bottom: 8px;
      margin-top: 18px;
      font-size: 1rem;
      color: rgba(148, 163, 184, 0.9);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .console-output pre {
      background: rgba(2, 6, 23, 0.95);
      border: 1px solid rgba(148, 163, 184, 0.35);
      padding: 12px;
      border-radius: 8px;
      overflow-x: auto;
      max-height: 320px;
      white-space: pre-wrap;
    }
    .hidden {
      display: none !important;
    }
    @media (max-width: 720px) {
      header {
        flex-direction: column;
        gap: 8px;
        align-items: flex-start;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Star Chart Generator</h1>
      <span class=\"subtle\">HTML control panel</span>
    </header>

    <section>
      <h2>Render configuration</h2>
      <form id=\"render-form\">
        <label>Configuration file
          <select id=\"config-select\" required></select>
        </label>
        <div class=\"row\">
          <label>Seed (optional)
            <input type=\"number\" id=\"seed-input\" placeholder=\"Use config seed\" />
          </label>
          <label class=\"checkbox\">
            <input type=\"checkbox\" id=\"save-toggle\" checked />
            Guardar PNG en la carpeta <code>output/</code>
          </label>
        </div>
        <button type=\"submit\" id=\"render-button\">Renderizar mapa estelar</button>
      </form>
      <div id=\"render-status\"></div>
      <div id=\"render-result\" class=\"hidden\">
        <img id=\"render-image\" alt=\"Rendered star chart\" />
        <div id=\"render-meta\" class=\"subtle\"></div>
      </div>
    </section>

    <section>
      <h2>Debug command console</h2>
      <p class=\"subtle\">Ejecuta código Python dentro del proyecto. Están disponibles <code>SceneConfig</code>, <code>generate_star_chart</code>, <code>PROJECT_ROOT</code>, <code>CONFIG_DIR</code> y <code>OUTPUT_DIR</code>.</p>
      <form id=\"debug-form\">
        <textarea id=\"debug-input\" placeholder=\"print('Hello, cosmos!')\"></textarea>
        <div class=\"row\">
          <button type=\"submit\" id=\"debug-run\">Ejecutar comando</button>
          <button type=\"button\" id=\"debug-clear\">Limpiar salida</button>
        </div>
      </form>
      <div class=\"console-output\">
        <h3>Stdout</h3>
        <pre id=\"debug-stdout\"></pre>
        <h3>Stderr</h3>
        <pre id=\"debug-stderr\"></pre>
      </div>
    </section>
  </main>

  <script>
    async function fetchConfigs() {
      const select = document.getElementById('config-select');
      select.innerHTML = '';
      try {
        const response = await fetch('/api/configs');
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.message || 'No se pudieron leer los archivos de configuración.');
        }
        if (!data.configs.length) {
          const option = document.createElement('option');
          option.value = '';
          option.textContent = 'No se encontraron archivos YAML en la carpeta de configuración';
          select.appendChild(option);
          select.disabled = true;
          return;
        }
        for (const item of data.configs) {
          const option = document.createElement('option');
          option.value = item;
          option.textContent = item;
          select.appendChild(option);
        }
      } catch (error) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = error.message;
        select.appendChild(option);
        select.disabled = true;
      }
    }

    async function renderChart(event) {
      event.preventDefault();
      const button = document.getElementById('render-button');
      const status = document.getElementById('render-status');
      const result = document.getElementById('render-result');
      const image = document.getElementById('render-image');
      const meta = document.getElementById('render-meta');
      const config = document.getElementById('config-select').value;
      const seed = document.getElementById('seed-input').value;
      const save = document.getElementById('save-toggle').checked;

      if (!config) {
        status.textContent = 'Selecciona un archivo de configuración.';
        return;
      }

      button.disabled = true;
      status.textContent = 'Renderizando, esto puede tardar varios minutos...';
      result.classList.add('hidden');

      try {
        const response = await fetch('/api/render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ config, seed, save })
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') {
          throw new Error(data.message || 'El render falló');
        }
        image.src = data.image_data_url;
        const seconds = Number(data.elapsed_seconds || 0).toFixed(2);
        const saved = data.saved_image ? ` • Guardado en ${data.saved_image}` : '';
        meta.textContent = `Tiempo de render: ${seconds}s${saved}`;
        status.textContent = 'Render completado.';
        result.classList.remove('hidden');
      } catch (error) {
        status.textContent = `❌ ${error.message}`;
        result.classList.add('hidden');
      } finally {
        button.disabled = false;
      }
    }

    async function runDebugCommand(event) {
      event.preventDefault();
      const runButton = document.getElementById('debug-run');
      const input = document.getElementById('debug-input');
      const stdout = document.getElementById('debug-stdout');
      const stderr = document.getElementById('debug-stderr');

      runButton.disabled = true;

      try {
        const response = await fetch('/api/debug', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command: input.value })
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'ok') {
          throw new Error(data.message || 'Fallo al ejecutar el comando');
        }
        stdout.textContent = data.stdout || '';
        stderr.textContent = data.stderr || '';
      } catch (error) {
        stderr.textContent = error.message;
      } finally {
        runButton.disabled = false;
      }
    }

    function clearDebugOutput() {
      document.getElementById('debug-stdout').textContent = '';
      document.getElementById('debug-stderr').textContent = '';
    }

    document.getElementById('render-form').addEventListener('submit', renderChart);
    document.getElementById('debug-form').addEventListener('submit', runDebugCommand);
    document.getElementById('debug-clear').addEventListener('click', clearDebugOutput);
    document.addEventListener('DOMContentLoaded', fetchConfigs);
  </script>
</body>
</html>
"""


def _list_configs(config_dir: Path) -> List[str]:
    patterns = ("*.yaml", "*.yml")
    items: List[str] = []
    for pattern in patterns:
        for path in sorted(config_dir.rglob(pattern)):
            if path.is_file():
                items.append(path.relative_to(config_dir).as_posix())
    return items


def _normalize_seed(seed: Optional[Any]) -> Optional[int]:
    if seed is None:
        return None
    if isinstance(seed, (int, float)):
        return int(seed)
    seed_str = str(seed).strip()
    if not seed_str:
        return None
    return int(seed_str)


def _ensure_within(path: Path, directory: Path) -> Path:
    resolved = path.resolve()
    directory = directory.resolve()
    if directory not in resolved.parents and resolved != directory:
        raise ValueError("Path escapes the configured directory")
    return resolved


def _execute_debug_command(command: str, namespace: Dict[str, Any]) -> Tuple[str, str]:
    command = command.replace("\r\n", "\n")
    stripped = command.strip()
    if not stripped:
        return "", ""

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    try:
        try:
            compiled = compile(stripped, "<debug-console>", "eval")
        except SyntaxError:
            compiled = compile(command, "<debug-console>", "exec")
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                exec(compiled, namespace, namespace)
        else:
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                result = eval(compiled, namespace, namespace)
                if result is not None:
                    print(repr(result))
    except Exception as exc:  # pragma: no cover - debugging helper
        if stderr_buffer.tell():
            stderr_buffer.write("\n")
        stderr_buffer.write(f"{exc.__class__.__name__}: {exc}")

    return stdout_buffer.getvalue(), stderr_buffer.getvalue()


class InterfaceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: Tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        project_root: Path,
        config_dir: Path,
        output_dir: Path,
    ) -> None:
        super().__init__(address, handler)
        self.project_root = project_root
        self.config_dir = config_dir
        self.output_dir = output_dir
        self.debug_globals: Dict[str, Any] = {
            "__builtins__": __builtins__,
            "PROJECT_ROOT": project_root,
            "CONFIG_DIR": config_dir,
            "OUTPUT_DIR": output_dir,
            "SceneConfig": SceneConfig,
            "generate_star_chart": generate_star_chart,
        }


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "StarChartUI/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # pragma: no cover - cosmetic
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send_bytes(self, payload: bytes, *, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self._send_bytes(data, content_type="application/json; charset=utf-8", status=status)

    def _handle_index(self) -> None:
        self._send_bytes(INDEX_HTML.encode("utf-8"), content_type="text/html; charset=utf-8")

    def _handle_list_configs(self) -> None:
        configs = _list_configs(self.server.config_dir)
        self._send_json({"configs": configs})

    def _parse_json_body(self) -> Dict[str, Any]:
        length_header = self.headers.get("Content-Length")
        if not length_header:
            raise ValueError("Missing Content-Length header")
        length = int(length_header)
        raw = self.rfile.read(length)
        if not raw:
            raise ValueError("Empty request body")
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON payload: {exc}") from exc

    def _handle_render(self) -> None:
        try:
            payload = self._parse_json_body()
            config_name = payload.get("config")
            if not config_name:
                raise ValueError("Missing 'config' field")
            config_path = _ensure_within(self.server.config_dir / config_name, self.server.config_dir)
            if not config_path.exists():
                raise FileNotFoundError(f"Config not found: {config_name}")

            seed = _normalize_seed(payload.get("seed"))
            save_output = bool(payload.get("save", False))

            config = SceneConfig.load(config_path)

            start = time.perf_counter()
            result = generate_star_chart(config, seed=seed)
            elapsed = time.perf_counter() - start

            png_bytes = result.image.to_png_bytes()
            encoded = base64.b64encode(png_bytes).decode("ascii")
            image_data_url = f"data:image/png;base64,{encoded}"

            saved_image: Optional[str] = None
            if save_output:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_dir = self.server.output_dir
                output_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{config_path.stem}_{timestamp}.png"
                output_path = output_dir / filename
                output_path.write_bytes(png_bytes)
                try:
                    saved_image = output_path.relative_to(self.server.project_root).as_posix()
                except ValueError:
                    saved_image = str(output_path)

            self._send_json(
                {
                    "status": "ok",
                    "image_data_url": image_data_url,
                    "elapsed_seconds": elapsed,
                    "saved_image": saved_image,
                }
            )
        except Exception as exc:  # pragma: no cover - error reporting path
            self._send_json(
                {"status": "error", "message": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )

    def _handle_debug(self) -> None:
        try:
            payload = self._parse_json_body()
            command = payload.get("command", "")
            stdout, stderr = _execute_debug_command(str(command), self.server.debug_globals)
            self._send_json({"status": "ok", "stdout": stdout, "stderr": stderr})
        except Exception as exc:  # pragma: no cover - error reporting path
            self._send_json(
                {"status": "error", "message": str(exc)},
                status=HTTPStatus.BAD_REQUEST,
            )

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._handle_index()
        elif parsed.path == "/api/configs":
            self._handle_list_configs()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/render":
            self._handle_render()
        elif parsed.path == "/api/debug":
            self._handle_debug()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:  # pragma: no cover - depends on environment
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the HTML interface for the star chart generator")
    parser.add_argument("--host", default="127.0.0.1", help="Host/interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="Port to listen on (default: auto)")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR, help="Directory that contains YAML configs")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory where rendered PNGs are saved")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the interface in a browser automatically")
    args = parser.parse_args()

    handler = RequestHandler
    server = InterfaceHTTPServer(
        (args.host, args.port),
        handler,
        project_root=PROJECT_ROOT,
        config_dir=args.config_dir,
        output_dir=args.output_dir,
    )

    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Star chart interface disponible en {url}")

    if not args.no_browser:
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive behaviour
        print("\nDetenido por el usuario.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
