"""Programmazione giornaliera in ora locale, indipendente dalle richieste HTTP."""

import logging
import os
import socket
import threading
import time

logger = logging.getLogger(__name__)


def is_scheduled_on(now, on_time, off_time):
    current = now.strftime("%H:%M")
    if on_time < off_time:
        return on_time <= current < off_time
    return current >= on_time or current < off_time


def notify_systemd(message):
    address = os.getenv("NOTIFY_SOCKET")
    if not address or not hasattr(socket, "AF_UNIX"):
        return
    if address.startswith("@"):
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.settimeout(0.2)
            client.connect(address)
            client.sendall(message.encode())
    except OSError:
        logger.warning("Notifica systemd non riuscita", exc_info=True)


class LampScheduler:
    def __init__(self, service, interval=1.0):
        self.service = service
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="lamp-scheduler", daemon=True)
        self.last_tick = None

    def start(self):
        self._thread.start()

    @property
    def healthy(self):
        return (self._thread.is_alive() and self.last_tick is not None
                and time.monotonic() - self.last_tick < max(5, self.interval * 3))

    def _run(self):
        while not self._stop.is_set():
            try:
                if not self.service.error:
                    self.service.tick()
                    self.last_tick = time.monotonic()
                    notify_systemd("WATCHDOG=1")
            except Exception:
                logger.exception("Errore dello scheduler")
                self.service.fail("Programmazione interrotta. Spegnimento richiesto; riavviare il servizio.")
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)
