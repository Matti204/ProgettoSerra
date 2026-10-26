"""SQLite: una configurazione atomica, nessuna accensione manuale persistita."""

import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass


def validate_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("Gli orari devono avere il formato HH:MM (00:00–23:59).")
    return value


@dataclass(frozen=True)
class LampSettings:
    mode: str = "manual"
    on_time: str = "08:00"
    off_time: str = "20:00"

    def __post_init__(self):
        if self.mode not in {"manual", "auto"}:
            raise ValueError("La modalità deve essere manual o auto.")
        validate_time(self.on_time)
        validate_time(self.off_time)
        if self.on_time == self.off_time:
            raise ValueError("Accensione e spegnimento devono avere orari diversi.")

    def to_dict(self):
        return asdict(self)


class SettingsStore:
    def __init__(self, path):
        self.path = path
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                mode TEXT NOT NULL CHECK (mode IN ('manual', 'auto')),
                on_time TEXT NOT NULL, off_time TEXT NOT NULL)""")
            db.execute("INSERT OR IGNORE INTO settings VALUES (1, 'manual', '08:00', '20:00')")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=3)

    def load(self):
        with closing(self._connect()) as db:
            row = db.execute("SELECT mode, on_time, off_time FROM settings WHERE id=1").fetchone()
        if row is None:
            raise ValueError("Configurazione persistente mancante.")
        return LampSettings(*row)

    def save(self, settings):
        with closing(self._connect()) as db, db:
            db.execute("UPDATE settings SET mode=?, on_time=?, off_time=? WHERE id=1",
                       (settings.mode, settings.on_time, settings.off_time))
