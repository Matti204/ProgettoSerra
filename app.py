"""Avvio: python app.py. Un processo, scheduler unico, nessun reloader."""

import atexit
import hmac
import ipaddress
import logging
import signal
import time
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from config import BASE_DIR, Settings
from hardware import make_controller
from scheduler import LampScheduler, notify_systemd
from services.instance_lock import InstanceLock
from services.lamp import LampService, ModeConflict, ServiceUnavailable
from services.sensors import SensorService
from services.storage import SettingsStore

logger = logging.getLogger(__name__)


def create_app(settings=None, *, start_scheduler=True, controller=None, clock=None):
    settings = settings or Settings.from_env()
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=4096, TRUSTED_HOSTS=list(settings.allowed_hosts))
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    instance_lock = InstanceLock(settings.data_dir / "server.lock")
    hardware = None
    try:
        hardware = controller or make_controller(settings)
        store = SettingsStore(settings.data_dir / "greenhouse.sqlite3")
        lamp = LampService(hardware, store, settings.timezone, clock)
    except Exception:
        if hardware is not None:
            hardware.close()
        instance_lock.close()
        raise
    scheduler = LampScheduler(lamp)
    sensors = SensorService(settings.hardware_mode == "mock")
    started_at = time.monotonic()
    closed = False

    def shutdown():
        nonlocal closed
        if not closed:
            closed = True
            try:
                scheduler.stop()
                lamp.close()
            finally:
                instance_lock.close()
                atexit.unregister(shutdown)

    app.extensions.update(lamp=lamp, scheduler=scheduler, settings=settings, shutdown=shutdown)
    atexit.register(shutdown)
    if start_scheduler:
        scheduler.start()

    def loopback_client():
        try:
            peer = ipaddress.ip_address(request.remote_addr or "")
            return peer.is_loopback and urlsplit(request.host_url).hostname in {"localhost", "127.0.0.1", "::1"}
        except ValueError:
            return False

    @app.before_request
    def protect_api():
        if not request.path.startswith("/api/"):
            return None
        # Reject cross-origin reads as well as writes; never enable CORS.
        origin = request.headers.get("Origin")
        if (origin and origin != request.host_url.rstrip("/")) or request.headers.get("Sec-Fetch-Site") == "cross-site":
            return jsonify(error="Origine della richiesta non consentita."), 403
        if settings.network_mode == "local" and not loopback_client():
            return jsonify(error="Accesso disponibile solo dal computer locale."), 403
        if settings.network_mode == "lan" and not loopback_client():
            supplied = request.headers.get("Authorization", "")
            expected = "Bearer " + settings.api_token
            if not hmac.compare_digest(supplied.encode(), expected.encode()):
                return jsonify(error="Token di accesso richiesto o non valido."), 401
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("X-Greenhouse-Request") != "1" or not request.is_json:
                return jsonify(error="Sono richiesti JSON e l'header X-Greenhouse-Request: 1."), 403
        return None

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/") or request.path in {"/", "/health"}:
            response.headers["Cache-Control"] = "no-store"
        return response

    def status():
        snapshot = lamp.snapshot()
        scheduler_ok = scheduler.healthy if start_scheduler else None
        return {
            "lamp": snapshot,
            "sensors": sensors.readings(),
            "system": {
                "hardware_mode": settings.hardware_mode, "network_mode": settings.network_mode,
                "timezone": settings.timezone, "server_time": lamp.now().isoformat(),
                "uptime_seconds": int(time.monotonic() - started_at),
                "scheduler_healthy": scheduler_ok,
                "healthy": not snapshot["error"] and (scheduler_ok is not False),
                "relay": {"pin": settings.relay_pin, "active_high": settings.relay_active_high,
                          "numbering": "BCM", "requires_restart": True},
            },
        }

    def payload(allowed, required):
        body = request.get_json()
        if not isinstance(body, dict) or set(body) - allowed or not required <= set(body):
            raise ValueError("Campi JSON mancanti o non riconosciuti.")
        if not body:
            raise ValueError("Specificare almeno un'impostazione.")
        return body

    @app.get("/")
    def dashboard():
        return render_template("index.html")

    @app.get("/health")
    def health():
        snapshot = lamp.snapshot()
        healthy = not snapshot["error"] and (not start_scheduler or scheduler.healthy)
        return jsonify(status="ok" if healthy else "degraded"), 200 if healthy else 503

    @app.get("/api/status")
    def api_status():
        return jsonify(status())

    @app.post("/api/lamp")
    def api_lamp():
        body = payload({"on"}, {"on"})
        lamp.set_manual(body["on"])
        return jsonify(status())

    @app.put("/api/settings")
    def api_settings():
        body = payload({"mode", "on_time", "off_time"}, set())
        if any(not isinstance(value, str) for value in body.values()):
            raise ValueError("Le impostazioni devono essere stringhe.")
        lamp.configure(body)
        return jsonify(status())

    @app.errorhandler(ModeConflict)
    def conflict(exc):
        return jsonify(error=str(exc)), 409

    @app.errorhandler(ValueError)
    def invalid(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(ServiceUnavailable)
    def unavailable(exc):
        return jsonify(error=str(exc)), 503

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error=exc.description), exc.code

    @app.errorhandler(Exception)
    def unexpected(exc):
        logger.exception("Errore applicativo non gestito")
        # Un errore inatteso durante un comando non deve lasciare il carico acceso.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            lamp.fail("Errore applicativo. Spegnimento richiesto; riavviare il servizio.")
        return jsonify(error="Errore interno del server. Controllare lo stato del sistema."), 500

    return app


def main():
    from waitress import create_server

    load_dotenv(BASE_DIR / ".env", override=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app()
    settings = app.extensions["settings"]
    server = None

    def terminate(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    try:
        server = create_server(app, host=settings.host, port=settings.port, threads=4,
                               connection_limit=32, backlog=64, channel_timeout=30,
                               max_request_body_size=4096)
        logger.info("Smart Greenhouse: http://localhost:%s | hardware=%s | rete=%s",
                    settings.port, settings.hardware_mode, settings.network_mode)
        notify_systemd("READY=1")
        server.run()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Arresto: spegnimento della lampada.")
    finally:
        notify_systemd("STOPPING=1")
        app.extensions["shutdown"]()
        if server:
            server.close()


if __name__ == "__main__":
    main()
