"""Sensori Linux sysfs: nessuna libreria GPIO, nessuna scrittura ai pin.

Il kernel deve essere configurato sul Raspberry con gli overlay w1-gpio e dht11.
Questi adapter leggono solo la temperatura DS18B20 e l'umidità DHT11.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path


class SensorReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Sample:
    value: float
    device_id: str


class DS18B20Reader:
    source = "DS18B20"

    def __init__(self, pin=4, device_id="", root=Path("/sys/bus/w1/devices")):
        if device_id and not re.fullmatch(r"28-[0-9a-fA-F]{12}", device_id):
            raise ValueError("ID DS18B20 non valido.")
        self.pin = pin
        self.device_id = device_id
        self.root = Path(root)

    def read(self):
        try:
            if self.device_id:
                selected = self.root / self.device_id
            else:
                candidates = sorted(path for path in self.root.glob("28-*")
                                    if re.fullmatch(r"28-[0-9a-fA-F]{12}", path.name) and path.is_dir())
                if not candidates:
                    raise SensorReadError("DS18B20 non rilevato. Verificare cablaggio e overlay 1-Wire.")
                if len(candidates) != 1:
                    raise SensorReadError("Più sonde DS18B20 rilevate: impostare DS18B20_ID nel file .env.")
                selected = candidates[0]
            lines = (selected / "w1_slave").read_text(encoding="ascii").splitlines()
            if len(lines) != 2 or not lines[0].endswith(" YES"):
                raise SensorReadError("DS18B20: lettura incompleta o CRC non valido.")
            match = re.search(r"\bt=(-?\d+)\s*$", lines[1])
            if not match:
                raise SensorReadError("DS18B20: temperatura assente o formato non valido.")
            value = int(match[1]) / 1000
            if not -55 <= value <= 125:
                raise SensorReadError("DS18B20: temperatura fuori dal campo del sensore.")
            return Sample(value, selected.name)
        except (OSError, UnicodeError) as exc:
            detail = exc.strerror if isinstance(exc, OSError) else "formato non valido"
            raise SensorReadError(f"DS18B20: lettura non riuscita ({detail}).") from exc


class DHT11Reader:
    source = "DHT11"

    def __init__(self, pin=22, device_id="", root=Path("/sys/bus/iio/devices")):
        if device_id and not re.fullmatch(r"iio:device\d+", device_id):
            raise ValueError("Identificativo IIO non valido.")
        self.pin = pin
        self.device_id = device_id
        self.root = Path(root)

    @staticmethod
    def _is_dht11(path):
        name = (path / "name").read_text(encoding="ascii").strip()
        return re.fullmatch(r"dht11(?:[.@:-][\w.@:-]+)?", name) is not None

    def read(self):
        try:
            if self.device_id:
                selected = self.root / self.device_id
                if not self._is_dht11(selected):
                    raise SensorReadError("Il dispositivo DHT11_DEVICE selezionato non è gestito dal driver dht11.")
            else:
                candidates = []
                for path in sorted(self.root.glob("iio:device*")):
                    try:
                        if self._is_dht11(path):
                            candidates.append(path)
                    except FileNotFoundError:
                        continue
                if not candidates:
                    raise SensorReadError("DHT11 non rilevato. Verificare l'overlay dht11 e il cablaggio.")
                if len(candidates) != 1:
                    raise SensorReadError("Più DHT11 rilevati: impostare DHT11_DEVICE nel file .env.")
                selected = candidates[0]
            # IIO restituisce millesimi di percentuale; il kernel verifica il checksum.
            raw = (selected / "in_humidityrelative_input").read_text(encoding="ascii").strip()
            if not re.fullmatch(r"\d+", raw):
                raise SensorReadError("DHT11: formato della lettura non valido.")
            value = int(raw) / 1000
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise SensorReadError("DHT11: umidità fuori dall'intervallo 0–100%.")
            return Sample(value, selected.name)
        except (OSError, UnicodeError) as exc:
            detail = exc.strerror if isinstance(exc, OSError) else "formato non valido"
            raise SensorReadError(f"DHT11: lettura non riuscita ({detail}). Verificare segnale e alimentazione.") from exc
