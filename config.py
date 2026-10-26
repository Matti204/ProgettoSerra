"""Configurazione comune a PC e Raspberry. Nessun rilevamento automatico GPIO."""

import os
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
        return cls(
            hardware_mode=mode,
            network_mode=os.getenv("NETWORK_MODE", "local").strip().lower(),
            port=int(os.getenv("PORT", "5000")),
            timezone=os.getenv("TIMEZONE", "Europe/Rome"),
            data_dir=data_dir if data_dir.is_absolute() else BASE_DIR / data_dir,
            relay_pin=int(os.getenv("RELAY_PIN", "17")),
            relay_active_high=polarity == "true",
            api_token=os.getenv("API_TOKEN", ""),
            allowed_hosts=tuple(
                host.strip() for host in os.getenv(
                    "ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
                ).split(",")
            ),
        )
