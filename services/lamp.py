import logging
import threading
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from hardware import HardwareError
from scheduler import is_scheduled_on

logger = logging.getLogger(__name__)


class ModeConflict(ValueError):
    pass


class ServiceUnavailable(RuntimeError):
    pass


class LampService:
    def __init__(self, controller, store, timezone, clock=None):
        self.controller = controller
        self.store = store
        self.timezone = ZoneInfo(timezone)
        self.clock = clock or (lambda: datetime.now(self.timezone))
        self._lock = threading.RLock()
        self.error = None
        self._closed = False
        self._manual_on = False
        self.updated_at = None
        self.controller.set_lamp(False)
        self.settings = self.store.load()  # Invalid/corrupt DB blocks startup; no reset.
        self.tick()

    def now(self):
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("L'orologio deve avere un fuso orario.")
        return now.astimezone(self.timezone)

    def _apply(self, desired):
        try:
            if self.controller.lamp_state() != desired:
                self.controller.set_lamp(desired)
            self.updated_at = self.now().isoformat()
        except HardwareError as exc:
            self.fail("Errore hardware. Spegnimento richiesto; verificare il relè e riavviare il servizio.")
            raise ServiceUnavailable(self.error) from exc

    def fail(self, message):
        with self._lock:
            if not self.error:
                logger.error(message)
            self.error = message
            self._manual_on = False
            try:
                self.controller.set_lamp(False)
            except Exception:
                logger.exception("Impossibile confermare il comando di spegnimento")

    def _check(self):
        if self._closed or self.error:
            raise ServiceUnavailable(self.error or "Servizio arrestato.")

    def tick(self):
        with self._lock:
            self._check()
            desired = (is_scheduled_on(self.now(), self.settings.on_time, self.settings.off_time)
                       if self.settings.mode == "auto" else self._manual_on)
            self._apply(desired)

    def set_manual(self, on):
        if type(on) is not bool:
            raise ValueError("Il campo on deve essere true o false.")
        with self._lock:
            self._check()
            if self.settings.mode != "manual":
                raise ModeConflict("Passa alla modalità manuale prima di comandare la lampada.")
            self._apply(on)
            self._manual_on = on
            return self.snapshot()

    def configure(self, changes):
        with self._lock:
            self._check()
            new_settings = replace(self.settings, **changes)
            try:
                self.store.save(new_settings)
            except Exception as exc:
                logger.exception("Salvataggio della configurazione fallito")
                self.fail("Salvataggio non riuscito. Spegnimento richiesto; controllare il disco e riavviare.")
                raise ServiceUnavailable(self.error) from exc
            if self.settings.mode != new_settings.mode:
                self._manual_on = False
            self.settings = new_settings
            self.tick()
            return self.snapshot()

    def snapshot(self):
        with self._lock:
            state = None
            try:
                state = self.controller.lamp_state()
            except HardwareError:
                self.fail("Stato GPIO non disponibile. Spegnimento richiesto; riavviare il servizio.")
            return {
                "on": state,
                "mode": self.settings.mode,
                "schedule": {"on_time": self.settings.on_time, "off_time": self.settings.off_time,
                             "overnight": self.settings.on_time > self.settings.off_time},
                "error": self.error,
                "updated_at": self.updated_at,
            }

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                self._manual_on = False
                self.controller.close()
