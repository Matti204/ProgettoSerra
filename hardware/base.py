from abc import ABC, abstractmethod


class HardwareError(RuntimeError):
    """Il comando non è stato completato: non assumere lo stato fisico del carico."""


class GPIOController(ABC):
    @abstractmethod
    def set_lamp(self, on: bool) -> None:
        pass

    @abstractmethod
    def lamp_state(self) -> bool:
        """Stato logico dell'uscita, non misura fisica della lampada."""

    @abstractmethod
    def close(self) -> None:
        pass
