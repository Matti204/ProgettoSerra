"""Adattatore GPIO Zero; importato soltanto quando HARDWARE_MODE=real."""

import platform
from pathlib import Path

from .base import GPIOController, HardwareError


class RealGPIOController(GPIOController):
    def __init__(self, pin, active_high, *, device_factory=None):
        self._device = None
        self._closed = False
        if type(pin) is not int or not 2 <= pin <= 27 or type(active_high) is not bool:
            raise ValueError("Pin BCM o polarità non validi.")
        try:
            if device_factory is None:
                model = Path("/proc/device-tree/model")
                if platform.system() != "Linux" or not model.exists() or "Raspberry Pi" not in model.read_text():
                    raise HardwareError("Hardware reale consentito solo su Raspberry Pi; usare mock sul PC.")
                from gpiozero import OutputDevice
                from gpiozero.pins.lgpio import LGPIOFactory
                # Backend esplicito: niente fallback a mock o controllo GPIO remoto.
                self._factory = LGPIOFactory()
                device_factory = lambda **kwargs: OutputDevice(pin_factory=self._factory, **kwargs)
            self._device = device_factory(pin=pin, active_high=active_high, initial_value=False)
            self._device.off()
        except Exception as exc:
            self.close()
            raise HardwareError("Inizializzazione GPIO fallita; verificare relè e permessi.") from exc

    def set_lamp(self, on):
        if type(on) is not bool:
            raise ValueError("Il comando lampada deve essere booleano.")
        if self._closed:
            raise HardwareError("Controller GPIO chiuso.")
        try:
            self._device.on() if on else self._device.off()
        except Exception as exc:
            try:
                self._device.off()
            except Exception:
                pass
            raise HardwareError("Comando GPIO fallito; spegnimento richiesto.") from exc

    def lamp_state(self):
        try:
            if self._closed:
                raise HardwareError("Controller GPIO chiuso.")
            return bool(self._device.value)
        except Exception as exc:
            raise HardwareError("Impossibile leggere lo stato logico GPIO.") from exc

    def close(self):
        try:
            if self._device is not None and not self._closed:
                try:
                    self._device.off()
                finally:
                    self._device.close()
        except Exception:
            # La chiusura è best effort; nessuna garanzia in caso di guasto fisico.
            import logging
            logging.getLogger(__name__).exception("Errore durante la chiusura GPIO")
        finally:
            self._closed = True
            factory = getattr(self, "_factory", None)
            if factory is not None:
                try:
                    factory.close()
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("Chiusura del backend GPIO fallita")
