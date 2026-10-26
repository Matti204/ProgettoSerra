import builtins
import sqlite3

import pytest

from app import create_app
from config import Settings
from hardware import HardwareError, MockGPIOController, make_controller
from hardware.real import RealGPIOController
from services.lamp import ServiceUnavailable
from services.sensors import SensorService


class FakeOutput:
    def __init__(self, *, pin, active_high, initial_value):
        self.pin = pin
        self.active_high = active_high
        self.value = initial_value
        self.closed = False

    @property
    def physical_high(self):
        return self.value == self.active_high

    def on(self):
        self.value = True

    def off(self):
        self.value = False

    def close(self):
        self.closed = True


@pytest.mark.parametrize("active_high", [True, False])
def test_real_adapter_polarity_safe_start_and_shutdown(active_high):
    outputs = []

    def factory(**kwargs):
        output = FakeOutput(**kwargs)
        outputs.append(output)
        return output

    controller = RealGPIOController(17, active_high, device_factory=factory)
    output = outputs[0]
    assert controller.lamp_state() is False
    assert output.physical_high is (not active_high)
    controller.set_lamp(True)
    assert controller.lamp_state() is True
    assert output.physical_high is active_high
    controller.close()
    controller.close()
    assert output.value is False
    assert output.closed


def test_real_initialization_failure_is_not_mock_fallback():
    def unavailable(**kwargs):
        raise OSError("Pin busy")
    with pytest.raises(HardwareError, match="Inizializzazione"):
        RealGPIOController(17, False, device_factory=unavailable)


def test_mock_does_not_import_gpiozero(monkeypatch):
    original_import = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.startswith(("gpiozero", "RPi", "lgpio")):
            raise AssertionError("L'ambiente locale non deve importare librerie GPIO")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    controller = make_controller(Settings())
    controller.set_lamp(True)
    assert controller.lamp_state() is True
    controller.close()


def test_absent_sensors_have_no_fabricated_measurements():
    assert all(reading["value"] is None and reading["status"] == "unavailable" for reading in SensorService(False).readings())


def test_hardware_failure_latches_fault_and_requests_off(app, client, command_headers, monkeypatch):
    lamp = app.extensions["lamp"]
    original_set = lamp.controller.set_lamp

    def fail_on(on):
        if on:
            raise HardwareError("Relay failed")
        original_set(False)
    monkeypatch.setattr(lamp.controller, "set_lamp", fail_on)
    assert client.post("/api/lamp", json={"on": True}, headers=command_headers).status_code == 503
    status = client.get("/api/status").json
    assert status["lamp"]["on"] is False
    assert status["lamp"]["error"]
    assert status["system"]["healthy"] is False
    assert client.get("/health").status_code == 503
    with pytest.raises(ServiceUnavailable):
        lamp.configure({"mode": "auto"})


def test_unknown_gpio_state_is_not_reported_off(app, client, monkeypatch):
    def fail_read():
        raise HardwareError("Cannot read GPIO")
    monkeypatch.setattr(app.extensions["lamp"].controller, "lamp_state", fail_read)
    status = client.get("/api/status").json
    assert status["lamp"]["on"] is None
    assert status["lamp"]["error"]


def test_storage_failure_turns_lamp_off(app, monkeypatch):
    lamp = app.extensions["lamp"]
    lamp.set_manual(True)

    def full_disk(settings):
        raise sqlite3.OperationalError("Disk full")
    monkeypatch.setattr(lamp.store, "save", full_disk)
    with pytest.raises(ServiceUnavailable):
        lamp.configure({"off_time": "19:00"})
    assert lamp.snapshot()["on"] is False
    assert lamp.error


def test_corrupt_database_blocks_start_and_leaves_controller_off(tmp_path):
    path = tmp_path / "greenhouse.sqlite3"
    path.write_bytes(b"corrupted data")
    controller = MockGPIOController()
    with pytest.raises(sqlite3.DatabaseError):
        create_app(Settings(data_dir=tmp_path), controller=controller, start_scheduler=False)
    assert controller._on is False
    assert controller._closed
    assert path.read_bytes() == b"corrupted data"


def test_shutdown_requests_off_and_stops_scheduler(app):
    controller = app.extensions["lamp"].controller
    app.extensions["lamp"].set_manual(True)
    app.extensions["shutdown"]()
    app.extensions["shutdown"]()
    assert controller._on is False
    assert controller._closed
