"""Importare questo modulo in mock non importa GPIO Zero."""

from .base import GPIOController, HardwareError
from .mock import MockGPIOController


def make_controller(settings):
    if settings.hardware_mode == "mock":
        return MockGPIOController()
    if settings.hardware_mode == "real":
        from .real import RealGPIOController
        return RealGPIOController(settings.relay_pin, settings.relay_active_high)
    raise ValueError("Modalità hardware non valida.")


__all__ = ["GPIOController", "HardwareError", "MockGPIOController", "make_controller"]
