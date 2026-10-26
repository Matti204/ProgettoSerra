from dataclasses import replace

import pytest

from app import create_app
from config import Settings


@pytest.mark.parametrize("headers", [
    {}, {"Origin": "http://evil.example", "X-Greenhouse-Request": "1"},
    {"Origin": "null", "X-Greenhouse-Request": "1"},
    {"Sec-Fetch-Site": "cross-site", "X-Greenhouse-Request": "1"},
])
def test_rejects_cross_site_or_simple_commands(client, headers):
    assert client.post("/api/lamp", json={"on": True}, headers=headers).status_code == 403
    assert client.get("/api/status").json["lamp"]["on"] is False


def test_host_validation_and_no_cors(client):
    assert client.get("/api/status", headers={"Host": "evil.example"}).status_code == 400
    response = client.options("/api/lamp", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 403
    assert "Access-Control-Allow-Origin" not in response.headers
    assert client.get("/api/status").headers["Cache-Control"] == "no-store"
    assert client.get("/api/status", environ_base={"REMOTE_ADDR": "192.168.1.10"}).status_code == 403


def test_lan_authentication_and_loopback_boundary(tmp_path):
    secret = "a-strong-random-test-token-at-least-32-chars"
    settings = Settings(data_dir=tmp_path, network_mode="lan", api_token=secret,
                        allowed_hosts=("localhost", "127.0.0.1", "greenhouse.local"))
    application = create_app(settings, start_scheduler=False)
    client = application.test_client()
    try:
        options = {"base_url": "http://greenhouse.local", "environ_base": {"REMOTE_ADDR": "192.168.1.20"}}
        assert client.get("/api/status", **options).status_code == 401
        assert client.get("/api/status", headers={"Authorization": "Bearer incorrect"}, **options).status_code == 401
        headers = {"Authorization": f"Bearer {secret}", "X-Greenhouse-Request": "1", "Origin": "http://greenhouse.local"}
        assert client.post("/api/lamp", json={"on": True}, headers=headers, **options).status_code == 200
        assert client.get("/api/status", headers=headers, **options).json["lamp"]["on"] is True
        assert client.get("/health", **options).status_code == 200
        # Spoofing Host does not bypass peer-address authentication.
        assert client.post("/api/lamp", json={"on": False}, headers={"Host": "127.0.0.1", "X-Greenhouse-Request": "1"}, environ_base={"REMOTE_ADDR": "192.168.1.20"}).status_code == 401
        # A local connection carrying a non-loopback host still needs the token.
        assert client.get("/api/status", base_url="http://greenhouse.local").status_code == 401
        assert client.get("/api/status", base_url="http://127.0.0.1").status_code == 200
        assert secret.encode() not in client.get("/").data
        assert secret not in str(client.get("/api/status").json)
    finally:
        application.extensions["shutdown"]()


@pytest.mark.parametrize("changes", [
    {"hardware_mode": "invalid"}, {"network_mode": "public"}, {"network_mode": "lan"},
    {"timezone": "Not/AZone"}, {"relay_pin": 99}, {"relay_active_high": "false"},
    {"allowed_hosts": ("*",)}, {"allowed_hosts": (".example.com",)}, {"port": 80},
])
def test_invalid_configuration_fails_closed(changes):
    with pytest.raises(ValueError):
        replace(Settings(), **changes)


def test_env_defaults_and_explicit_real_config(monkeypatch):
    for name in ["HARDWARE_MODE", "NETWORK_MODE", "PORT", "RELAY_PIN", "RELAY_ACTIVE_HIGH", "TIMEZONE", "ALLOWED_HOSTS"]:
        monkeypatch.delenv(name, raising=False)
    assert Settings.from_env().hardware_mode == "mock"
    monkeypatch.setenv("HARDWARE_MODE", "real")
    with pytest.raises(ValueError, match="specificare"):
        Settings.from_env()
    monkeypatch.setenv("RELAY_PIN", "17")
    monkeypatch.setenv("RELAY_ACTIVE_HIGH", "false")
    assert Settings.from_env().relay_active_high is False
    monkeypatch.setenv("RELAY_ACTIVE_HIGH", "maybe")
    with pytest.raises(ValueError):
        Settings.from_env()
