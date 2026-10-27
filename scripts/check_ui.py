"""Smoke test UI con Chrome DevTools, browser esistente e backend mock isolato.

Installare requirements-ui.txt. Non richiede Node, driver o download di browser.
Avvio: python scripts/check_ui.py. Screenshot in artifacts/ui/.
"""

import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

import websocket

ROOT = Path(__file__).resolve().parents[1]
OPENER = build_opener(ProxyHandler({}))
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def wait_for(check, description, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, URLError, ValueError, KeyError):
            pass
        time.sleep(.1)
    raise AssertionError(f"Timeout: {description}")


def get_json(url):
    with OPENER.open(url, timeout=1) as response:
        return json.load(response)


def find_browser():
    candidates = [os.environ.get("CHROME_PATH"), shutil.which("google-chrome"),
                  shutil.which("chromium"), shutil.which("chromium-browser"),
                  "C:/Program Files/Google/Chrome/Application/chrome.exe",
                  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    for name in candidates:
        if name and Path(name).is_file():
            return name
    raise SystemExit("Chrome/Chromium/Edge non trovato. Imposta CHROME_PATH al suo eseguibile.")


class CDP:
    def __init__(self, endpoint):
        self.ws = websocket.create_connection(endpoint, timeout=10, suppress_origin=True)
        self.sequence = 0
        self.errors = []

    def call(self, method, **params):
        self.sequence += 1
        current = self.sequence
        self.ws.send(json.dumps({"id": current, "method": method, "params": params}))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("method") == "Runtime.exceptionThrown":
                self.errors.append(reply["params"])
            if reply.get("id") == current:
                if "error" in reply:
                    raise AssertionError(reply["error"])
                return reply.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if result.get("exceptionDetails"):
            raise AssertionError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def until(self, expression, description):
        return wait_for(lambda: self.evaluate(expression), description)

    def screenshot(self, name, width, height):
        self.call("Emulation.setDeviceMetricsOverride", width=width, height=height,
                  deviceScaleFactor=1, mobile=False)
        self.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        assert self.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"Overflow orizzontale: {name}"
        png = self.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        (ROOT / "artifacts" / "ui" / name).write_bytes(base64.b64decode(png["data"]))


def main():
    browser_path = find_browser()
    output = ROOT / "artifacts" / "ui"
    output.mkdir(parents=True, exist_ok=True)
    # Seleziona una porta locale libera; i dati non toccano il progetto dell'utente.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    target = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="greenhouse-ui-", dir=output) as tmp:
        work = Path(tmp)
        env = {**os.environ, "HARDWARE_MODE": "mock", "NETWORK_MODE": "local",
               "DATA_DIR": str(work / "data"), "PORT": str(port), "TIMEZONE": "Europe/Rome",
               "ALLOWED_HOSTS": "localhost,127.0.0.1,[::1]", "API_TOKEN": "",
               "RELAY_PIN": "17", "RELAY_ACTIVE_HIGH": "false"}
        browser = None
        backend = None
        cdp = None
        with (output / "server.log").open("w") as log:
            def start_backend():
                return subprocess.Popen([sys.executable, str(ROOT / "app.py")], cwd=ROOT,
                                        env=env, stdout=log, stderr=log, creationflags=HIDDEN)

            backend = start_backend()
            try:
                wait_for(lambda: get_json(target + "/health")["status"] == "ok", "avvio server")
                profile = work / "browser"
                browser = subprocess.Popen([
                    browser_path, "--headless=new", "--remote-debugging-port=0",
                    f"--user-data-dir={profile}", "--disable-extensions", "--disable-background-networking",
                    "--no-first-run", "--no-default-browser-check", "about:blank",
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=HIDDEN)
                port_file = profile / "DevToolsActivePort"
                debug_port = wait_for(lambda: port_file.read_text().splitlines()[0], "avvio browser")
                pages = get_json(f"http://127.0.0.1:{debug_port}/json/list")
                page = next(page for page in pages if page["type"] == "page")
                cdp = CDP(page["webSocketDebuggerUrl"])
                cdp.call("Page.enable")
                cdp.call("Runtime.enable")
                cdp.call("Emulation.setDeviceMetricsOverride", width=1440, height=1080, deviceScaleFactor=1, mobile=False)
                cdp.call("Page.navigate", url=target)
                cdp.until("document.getElementById('connection-text')?.textContent === 'Connesso'", "dashboard connessa")
                assert "simulazione" in cdp.evaluate("document.getElementById('environment-text').textContent").lower()
                assert "24,6" in cdp.evaluate("document.getElementById('temperature-value').textContent")
                cdp.evaluate("document.getElementById('lamp-toggle').click()")
                cdp.until("document.getElementById('lamp-state').textContent === 'Accesa' && !document.getElementById('mode-auto').disabled", "accensione manuale")
                assert get_json(target + "/api/status")["lamp"]["on"] is True
                cdp.evaluate("document.getElementById('lamp-toggle').click()")
                cdp.until("document.getElementById('lamp-state').textContent === 'Spenta' && !document.getElementById('mode-auto').disabled", "spegnimento manuale")
                cdp.evaluate("document.getElementById('on-time').value='22:00'; document.getElementById('off-time').value='06:00'; document.getElementById('on-time').dispatchEvent(new Event('input',{bubbles:true})); document.getElementById('save-schedule').click()")
                cdp.until("document.getElementById('schedule-feedback').textContent.includes('correttamente') && !document.getElementById('mode-auto').disabled", "salvataggio fascia notturna")
                assert get_json(target + "/api/status")["lamp"]["schedule"]["overnight"]
                cdp.evaluate("document.getElementById('mode-auto').click()")
                cdp.until("document.getElementById('mode-auto').getAttribute('aria-pressed') === 'true' && !document.getElementById('mode-manual').disabled", "modalità automatica")
                assert cdp.evaluate("document.getElementById('lamp-toggle').disabled")
                cdp.evaluate("document.getElementById('mode-manual').click()")
                cdp.until("document.getElementById('mode-manual').getAttribute('aria-pressed') === 'true' && !document.getElementById('lamp-toggle').disabled", "ritorno manuale")
                assert cdp.evaluate("document.getElementById('lamp-state').textContent") == "Spenta"
                # Il polling non sovrascrive modifiche non ancora salvate.
                cdp.evaluate("document.getElementById('on-time').value='21:30'; document.getElementById('on-time').dispatchEvent(new Event('input',{bubbles:true}))")
                cdp.evaluate("new Promise(resolve => setTimeout(resolve, 3300))")
                assert cdp.evaluate("document.getElementById('on-time').value") == "21:30"
                cdp.evaluate("document.getElementById('on-time').value='06:00'; document.getElementById('save-schedule').click()")
                assert "diversi" in cdp.evaluate("document.getElementById('schedule-feedback').textContent")
                # Screenshot dello stato salvato, senza modifica pendente.
                cdp.evaluate("document.getElementById('on-time').value='22:00'; delete document.getElementById('schedule-form').dataset.dirty; document.getElementById('schedule-feedback').textContent=''")
                cdp.evaluate("document.getElementById('toast').hidden=true")
                cdp.screenshot("desktop.png", 1440, 1080)
                cdp.screenshot("touchscreen.png", 800, 480)
                assert cdp.evaluate("document.getElementById('lamp-toggle').getBoundingClientRect().bottom <= window.innerHeight"), "Il comando lampada deve essere visibile sul touchscreen 800x480"
                cdp.screenshot("mobile.png", 390, 844)
                # Interruzione vera del processo HTTP; il browser deve recuperare da solo.
                backend.terminate()
                backend.wait(timeout=10)
                cdp.until("document.getElementById('connection-text').textContent === 'Non connesso'", "rilevamento offline")
                assert cdp.evaluate("document.getElementById('lamp-toggle').disabled")
                assert cdp.evaluate("document.getElementById('temperature-value').textContent") == "Non disponibile"
                backend = start_backend()
                cdp.until("document.getElementById('connection-text').textContent === 'Connesso'", "riconnessione automatica")
                assert not cdp.evaluate("document.getElementById('lamp-toggle').disabled")
                # Fixture solo del test: verifica rendering delle nuove letture reali
                # senza importare driver o collegare sensori al computer.
                sensor_render = cdp.evaluate("""(() => {
                    authNeeded = true;
                    const fixture = structuredClone(state);
                    fixture.system.hardware_mode = 'real';
                    fixture.system.sensors_healthy = true;
                    Object.assign(fixture.sensors[0], {value:19.125, source:'DS18B20', status:'ok', configured:true, gpio:4, sampled_at:fixture.system.server_time});
                    Object.assign(fixture.sensors[1], {value:73, source:'DHT11', status:'ok', configured:true, gpio:22, sampled_at:fixture.system.server_time});
                    render(fixture);
                    const good = document.getElementById('temperature-tag').textContent === 'DS18B20'
                        && document.getElementById('humidity-tag').textContent === 'DHT11'
                        && document.getElementById('temperature-note').textContent.includes('lettura delle');
                    fixture.sensors[0].value = null;
                    fixture.sensors[0].status = 'stale';
                    fixture.sensors[0].message = 'Lettura scaduta.';
                    fixture.sensors[1].value = null;
                    fixture.sensors[1].status = 'error';
                    fixture.sensors[1].message = 'DHT11 non risponde.';
                    fixture.system.sensors_healthy = false;
                    render(fixture);
                    const failed = document.getElementById('temperature-value').textContent === 'Non disponibile'
                        && document.getElementById('temperature-tag').textContent === 'Scaduto'
                        && document.getElementById('humidity-note').textContent === 'DHT11 non risponde.'
                        && !document.getElementById('lamp-toggle').disabled;
                    authNeeded = false;
                    return good && failed;
                })()""")
                assert sensor_render, "Rendering di letture reali, errori e scadenza"
                cdp.evaluate("refresh()")
                assert not cdp.errors, f"Errori JavaScript: {cdp.errors}"
                print("UI OK: comandi, orari, sensori/errori/scadenza, polling, offline/recupero, desktop 1440, touch 800, mobile 390.")
                print(f"Screenshot: {output}")
            finally:
                if cdp:
                    try:
                        cdp.call("Browser.close")
                    except (OSError, ValueError, websocket.WebSocketException):
                        pass
                    cdp.ws.close()
                for process in [browser, backend]:
                    if process and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                # Lascia a Chromium il tempo di chiudere i suoi processi del profilo.
                time.sleep(.5)


if __name__ == "__main__":
    main()
