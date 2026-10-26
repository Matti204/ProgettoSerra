import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import create_app
from config import Settings
from scheduler import is_scheduled_on


@pytest.mark.parametrize("start,end,hour,minute,expected", [
    ("08:00", "20:00", 7, 59, False), ("08:00", "20:00", 8, 0, True),
    ("08:00", "20:00", 19, 59, True), ("08:00", "20:00", 20, 0, False),
    ("22:00", "06:00", 21, 59, False), ("22:00", "06:00", 22, 0, True),
    ("22:00", "06:00", 0, 0, True), ("22:00", "06:00", 5, 59, True),
    ("22:00", "06:00", 6, 0, False), ("22:00", "06:00", 12, 0, False),
    ("00:00", "00:01", 0, 0, True), ("00:00", "00:01", 0, 1, False),
])
def test_schedule_boundaries(start, end, hour, minute, expected):
    now = datetime(2026, 10, 26, hour, minute, tzinfo=ZoneInfo("Europe/Rome"))
    assert is_scheduled_on(now, start, end) is expected


def test_dst_is_local_wall_clock():
    # L'ora ripetuta in autunno segue la stessa fascia in entrambe le occorrenze.
    for fold in [0, 1]:
        now = datetime(2026, 10, 25, 2, 30, fold=fold, tzinfo=ZoneInfo("Europe/Rome"))
        assert is_scheduled_on(now, "02:00", "03:00")
    # Nessun evento da perdere: il primo tick dopo il salto ricalcola lo stato.
    now = datetime(2026, 3, 29, 3, 0, tzinfo=ZoneInfo("Europe/Rome"))
    assert is_scheduled_on(now, "02:30", "04:00")


def test_automatic_settings_restore_but_manual_on_does_not(tmp_path, clock):
    settings = Settings(data_dir=tmp_path)
    first = create_app(settings, start_scheduler=False, clock=clock)
    first.extensions["lamp"].configure({"mode": "auto", "on_time": "11:00", "off_time": "13:00"})
    first.extensions["shutdown"]()
    second = create_app(settings, start_scheduler=False, clock=clock)
    try:
        lamp = second.extensions["lamp"]
        assert lamp.snapshot()["on"] is True
        assert lamp.snapshot()["schedule"]["on_time"] == "11:00"
        lamp.configure({"mode": "manual"})
        lamp.set_manual(True)
    finally:
        second.extensions["shutdown"]()
    third = create_app(settings, start_scheduler=False, clock=clock)
    try:
        assert third.extensions["lamp"].snapshot()["on"] is False
        assert third.extensions["lamp"].snapshot()["mode"] == "manual"
    finally:
        third.extensions["shutdown"]()


def test_scheduler_runs_without_browser(tmp_path, clock):
    application = create_app(Settings(data_dir=tmp_path), clock=clock)
    lamp = application.extensions["lamp"]
    try:
        lamp.configure({"mode": "auto"})
        assert lamp.snapshot()["on"] is True
        clock.at(20)
        deadline = time.monotonic() + 3
        while lamp.snapshot()["on"] and time.monotonic() < deadline:
            time.sleep(.02)
        assert lamp.snapshot()["on"] is False
        assert application.extensions["scheduler"].healthy
    finally:
        application.extensions["shutdown"]()


def test_concurrent_manual_commands_are_serialized(app):
    lamp = app.extensions["lamp"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lamp.set_manual, [True, False] * 12))
    assert all(isinstance(result["on"], bool) for result in results)
    lamp.set_manual(False)
    assert lamp.snapshot()["on"] is False


def test_only_one_process_per_data_directory(app):
    with pytest.raises(RuntimeError, match="altra istanza"):
        create_app(app.extensions["settings"], start_scheduler=False)
