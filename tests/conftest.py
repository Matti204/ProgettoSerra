from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import create_app
from config import Settings


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 26, 12, 0, tzinfo=ZoneInfo("Europe/Rome"))

    def __call__(self):
        return self.value

    def at(self, hour, minute=0):
        self.value = self.value.replace(hour=hour, minute=minute)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def app(tmp_path, clock):
    application = create_app(Settings(data_dir=tmp_path), start_scheduler=False, clock=clock)
    application.config["TESTING"] = True
    yield application
    application.extensions["shutdown"]()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def command_headers():
    return {"X-Greenhouse-Request": "1", "Origin": "http://localhost"}
