"""Un worker per sensore: API e controllo lampada non aspettano l'I/O hardware."""

import logging
import math
import threading
import time
from datetime import datetime, timezone

from hardware.sensors import DHT11Reader, DS18B20Reader, SensorReadError

logger = logging.getLogger(__name__)
POLL_SECONDS = 5.0
STALE_SECONDS = 20.0
METRICS = (("temperature", "Temperatura", "°C", "DS18B20"),
           ("humidity", "Umidità", "%", "DHT11"))


class SensorWorker:
    def __init__(self, reader, *, interval=POLL_SECONDS, stale_after=STALE_SECONDS,
                 monotonic=time.monotonic, wall_clock=None):
        self.reader = reader
        self.interval = interval
        self.stale_after = stale_after
        self.monotonic = monotonic
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name=f"sensor-{reader.source}", daemon=True)
        self._state = {"value": None, "status": "pending", "message": "In attesa della prima lettura.",
                       "sampled_at": None, "device_id": reader.device_id or None}
        self._last_success = None
        self._created_at = self.monotonic()

    def start(self):
        self._thread.start()

    def poll_once(self):
        # Nessun lock durante l'I/O: API e lampada non aspettano il sensore.
        try:
            sample = self.reader.read()
            if type(sample.value) not in {float, int} or not math.isfinite(sample.value):
                raise SensorReadError("Il sensore ha restituito una misura non valida.")
            stamp = self.wall_clock().isoformat()
            now = self.monotonic()
            with self._lock:
                if self._stop.is_set():
                    return
                previous = self._state["status"]
                self._state.update(value=sample.value, status="ok", message="Lettura disponibile.",
                                   sampled_at=stamp, device_id=sample.device_id)
                self._last_success = now
            if previous in {"error", "stale"}:
                logger.info("%s: letture ripristinate", self.reader.source)
        except Exception as exc:
            message = str(exc) if isinstance(exc, SensorReadError) else f"{self.reader.source}: errore di acquisizione. Controllare il journal."
            with self._lock:
                if self._stop.is_set():
                    return
                changed = self._state["status"] != "error" or self._state["message"] != message
                self._state.update(value=None, status="error", message=message)
            if changed:
                logger.warning("%s: %s", self.reader.source, message, exc_info=not isinstance(exc, SensorReadError))

    def snapshot(self):
        with self._lock:
            result = dict(self._state)
            age = None if self._last_success is None else max(0, self.monotonic() - self._last_success)
        result["age_seconds"] = None if age is None else round(age, 1)
        if result["status"] == "ok" and age >= self.stale_after:
            result.update(value=None, status="stale", message="Lettura scaduta. In attesa di nuovi dati dal sensore.")
        elif result["status"] == "pending" and self.monotonic() - self._created_at >= self.stale_after:
            result.update(status="stale", message="Il sensore non risponde. Controllare il collegamento e il journal.")
        return result

    def _run(self):
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.interval)

    def request_stop(self):
        self._stop.set()

    def join(self):
        if self._thread.is_alive():
            self._thread.join(timeout=.5)


class SensorService:
    def __init__(self, simulated, readers=None, **worker_options):
        self.simulated = simulated
        self.workers = {} if simulated else {
            key: SensorWorker(reader, **worker_options) for key, reader in (readers or {}).items()
        }

    @classmethod
    def from_settings(cls, settings):
        if settings.hardware_mode == "mock":
            return cls(True)  # Nessuna scansione sysfs o import di librerie GPIO sul PC.
        readers = {}
        if settings.ds18b20_enabled:
            readers["temperature"] = DS18B20Reader(settings.ds18b20_pin, settings.ds18b20_id)
        if settings.dht11_enabled:
            readers["humidity"] = DHT11Reader(settings.dht11_pin, settings.dht11_device)
        return cls(False, readers)

    def start(self):
        for worker in self.workers.values():
            worker.start()

    def readings(self):
        result = []
        for key, label, unit, source in METRICS:
            row = {"id": key, "label": label, "unit": unit, "source": source,
                   "value": None, "status": "unavailable", "configured": False,
                   "sampled_at": None, "age_seconds": None, "device_id": None, "gpio": None,
                   "message": f"{source} non abilitato nella configurazione."}
            if self.simulated:
                row.update(value=24.6 if key == "temperature" else 62, status="simulated",
                           message="Dato dimostrativo, non misurato.")
            elif key in self.workers:
                worker = self.workers[key]
                row.update(worker.snapshot())
                row.update(configured=True, gpio=worker.reader.pin)
            result.append(row)
        return result

    def close(self):
        for worker in self.workers.values():
            worker.request_stop()
        for worker in self.workers.values():
            worker.join()
