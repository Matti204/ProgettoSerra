"""Supervisore Kiosk separato da Flask. Da avviare nella sessione grafica del Pi.

Una piccola pagina locale rimane disponibile anche quando Flask non è avviato.
Se il backend cade, riapre l'attesa; se Chromium termina, lo riavvia.
"""

import json
import logging
import platform
import shutil
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import Settings  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from services.instance_lock import InstanceLock  # noqa: E402

logger = logging.getLogger(__name__)


def main():
    if platform.system() != "Linux" or not Path("/proc/device-tree/model").exists():
        raise SystemExit("Il supervisore Kiosk è destinato al Raspberry; sul PC aprire localhost:5000.")
    load_dotenv(ROOT / ".env", override=False)
    settings = Settings.from_env()
    target = f"http://127.0.0.1:{settings.port}"
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chromium:
        raise SystemExit("Chromium non installato.")
    profile = Path.home() / ".local" / "share" / "smart-greenhouse" / "chromium"
    profile.mkdir(parents=True, exist_ok=True)
    try:
        lock = InstanceLock(profile.parent / "kiosk.lock")
    except RuntimeError:
        return  # Autostart XDG e labwc possono entrambi richiedere l'avvio.
    stop = threading.Event()
    opener = build_opener(ProxyHandler({}))

    def ready():
        try:
            with opener.open(target + "/health", timeout=2) as response:
                return response.status == 200
        except HTTPError as exc:
            return exc.code == 503  # Il dashboard deve mostrare anche gli errori hardware.
        except (OSError, URLError):
            return False

    class RecoveryHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host") != "127.0.0.1:5001":
                self.send_error(400)
                return
            if self.path == "/ready":
                content = json.dumps({"ready": ready()}).encode()
                content_type = "application/json"
            elif self.path == "/":
                content = (ROOT / "deploy" / "kiosk-wait.html").read_bytes()
                content_type = "text/html; charset=utf-8"
            elif self.path == "/wait.js":
                content = ("setInterval(async()=>{try{const r=await fetch('/ready',{cache:'no-store'});"
                           "const d=await r.json();if(d.ready)location.replace(" + json.dumps(target) + ");}catch{}},2000);").encode()
                content_type = "application/javascript"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 5001), RecoveryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = None

    def close_browser():
        if browser and browser.poll() is None:
            browser.terminate()
            try:
                browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser.kill()
                browser.wait(timeout=3)

    def on_signal(signum, frame):
        stop.set()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    was_ready = False
    try:
        while not stop.is_set():
            available = ready()
            if was_ready and not available:
                close_browser()
            if browser is None or browser.poll() is not None:
                browser = subprocess.Popen([
                    chromium, "--kiosk", "--noerrdialogs", "--no-first-run",
                    "--disable-session-crashed-bubble", "--password-store=basic",
                    f"--user-data-dir={profile}", "http://127.0.0.1:5001/",
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            was_ready = available
            stop.wait(4)
    finally:
        close_browser()
        server.shutdown()
        server.server_close()
        lock.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
