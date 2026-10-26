from .base import GPIOController, HardwareError


class MockGPIOController(GPIOController):
    def __init__(self):
        self._on = False
        self._closed = False

    def set_lamp(self, on):
        if self._closed:
            raise HardwareError("Controller simulato chiuso.")
        if type(on) is not bool:
            raise ValueError("Il comando lampada deve essere booleano.")
        self._on = on

    def lamp_state(self):
        if self._closed:
            raise HardwareError("Controller simulato chiuso.")
        return self._on

    def close(self):
        self._on = False
        self._closed = True
