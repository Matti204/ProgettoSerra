"""Configurazione comune a PC e Raspberry. Nessun rilevamento automatico GPIO."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    hardware_mode: str = "mock"
    network_mode: str = "local"
    port: int = 5000
    timezone: str = "Europe/Rome"
    data_dir: Path = BASE_DIR / "data"
    relay_pin: int = 17
    relay_active_high: bool = False
    api_token: str = ""
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "[::1]")
    ds18b20_enabled: bool = False
    ds18b20_pin: int = 4
    ds18b20_id: str = ""
    dht11_enabled: bool = False
    dht11_pin: int = 22
    dht11_device: str = ""

    def __post_init__(self):
        if self.hardware_mode not in {"mock", "real"}:
            raise ValueError("HARDWARE_MODE deve essere mock o real; avvio annullato.")
        if self.network_mode not in {"local", "lan"}:
            raise ValueError("NETWORK_MODE deve essere local o lan.")
        if type(self.port) is not int or not 1024 <= self.port <= 65535:
            raise ValueError("PORT deve essere compresa tra 1024 e 65535.")
        if type(self.relay_pin) is not int or not 2 <= self.relay_pin <= 27:
            raise ValueError("RELAY_PIN deve essere un GPIO BCM tra 2 e 27.")
        if type(self.relay_active_high) is not bool:
            raise ValueError("RELAY_ACTIVE_HIGH deve essere true o false.")
        if type(self.ds18b20_enabled) is not bool or type(self.dht11_enabled) is not bool:
            raise ValueError("DS18B20_ENABLED e DHT11_ENABLED devono essere true o false.")
        for name, pin in (("DS18B20_PIN", self.ds18b20_pin), ("DHT11_PIN", self.dht11_pin)):
            if type(pin) is not int or not 2 <= pin <= 27:
                raise ValueError(f"{name} deve essere un GPIO BCM tra 2 e 27.")
        if not isinstance(self.ds18b20_id, str) or (self.ds18b20_id and not re.fullmatch(r"28-[0-9a-fA-F]{12}", self.ds18b20_id)):
            raise ValueError("DS18B20_ID deve essere vuoto oppure un ID come 28-000000abcdef.")
        if not isinstance(self.dht11_device, str) or (self.dht11_device and not re.fullmatch(r"iio:device\d+", self.dht11_device)):
            raise ValueError("DHT11_DEVICE deve essere vuoto oppure un nome come iio:device0.")
        occupied = {}
        if self.hardware_mode == "real":
            occupied[self.relay_pin] = "relè"
        for enabled, pin, label in ((self.ds18b20_enabled, self.ds18b20_pin, "DS18B20"),
                                    (self.dht11_enabled, self.dht11_pin, "DHT11")):
            if enabled:
                if pin in occupied:
                    raise ValueError(f"GPIO BCM {pin} condiviso tra {occupied[pin]} e {label}: scegliere pin distinti.")
                occupied[pin] = label
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("TIMEZONE non riconosciuta.") from exc
        if self.network_mode == "lan" and len(self.api_token) < 32:
            raise ValueError("In LAN impostare API_TOKEN con almeno 32 caratteri casuali.")
        if not self.allowed_hosts or any(
            not host or host.startswith(".") or any(c in host for c in "/*@?# ")
            for host in self.allowed_hosts
        ):
            raise ValueError("ALLOWED_HOSTS deve contenere nomi o IP espliciti senza wildcard.")

    @property
    def host(self):
        return "127.0.0.1" if self.network_mode == "local" else "0.0.0.0"

    @classmethod
    def from_env(cls):
        mode = os.getenv("HARDWARE_MODE", "mock").strip().lower()
        polarity = os.getenv("RELAY_ACTIVE_HIGH", "false").strip().lower()
        if polarity not in {"true", "false"}:
            raise ValueError("RELAY_ACTIVE_HIGH deve essere true o false.")
        if mode == "real" and any(
            not os.getenv(key, "").strip() for key in ("RELAY_PIN", "RELAY_ACTIVE_HIGH")
        ):
            raise ValueError("In modalità real specificare RELAY_PIN e RELAY_ACTIVE_HIGH.")
        data_dir = Path(os.getenv("DATA_DIR", "data"))

        def flag(name):
            value = os.getenv(name, "false").strip().lower()
            if value not in {"true", "false"}:
                raise ValueError(f"{name} deve essere true o false.")
            return value == "true"

        return cls(
            hardware_mode=mode,
            network_mode=os.getenv("NETWORK_MODE", "local").strip().lower(),
            port=int(os.getenv("PORT", "5000")),
            timezone=os.getenv("TIMEZONE", "Europe/Rome"),
            data_dir=data_dir if data_dir.is_absolute() else BASE_DIR / data_dir,
            relay_pin=int(os.getenv("RELAY_PIN", "17")),
            relay_active_high=polarity == "true",
            api_token=os.getenv("API_TOKEN", ""),
            ds18b20_enabled=flag("DS18B20_ENABLED"),
            ds18b20_pin=int(os.getenv("DS18B20_PIN", "4")),
            ds18b20_id=os.getenv("DS18B20_ID", "").strip(),
            dht11_enabled=flag("DHT11_ENABLED"),
            dht11_pin=int(os.getenv("DHT11_PIN", "22")),
            dht11_device=os.getenv("DHT11_DEVICE", "").strip(),
            allowed_hosts=tuple(
                host.strip() for host in os.getenv(
                    "ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
                ).split(",")
            ),
        )
