import pytest


def test_dashboard_and_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Smart Greenhouse" in response.data
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200


def test_mock_initial_state_and_manual_controls(client, command_headers):
    initial = client.get("/api/status").json
    assert initial["lamp"]["on"] is False
    assert initial["system"]["hardware_mode"] == "mock"
    assert all(sensor["status"] == "simulated" for sensor in initial["sensors"])
    for on in [True, False, False, True]:
        response = client.post("/api/lamp", json={"on": on}, headers=command_headers)
        assert response.status_code == 200
        assert response.json["lamp"]["on"] is on
    assert client.get("/api/status").json["lamp"]["on"] is True


def test_automatic_mode_rejects_manual_command(client, command_headers, clock, app):
    response = client.put("/api/settings", json={"mode": "auto"}, headers=command_headers)
    assert response.json["lamp"]["on"] is True  # Noon inside default interval.
    assert client.post("/api/lamp", json={"on": False}, headers=command_headers).status_code == 409
    clock.at(20)
    app.extensions["lamp"].tick()
    assert client.get("/api/status").json["lamp"]["on"] is False
    clock.at(12)
    app.extensions["lamp"].tick()
    assert client.get("/api/status").json["lamp"]["on"] is True
    response = client.put("/api/settings", json={"mode": "manual"}, headers=command_headers)
    assert response.json["lamp"]["on"] is False


@pytest.mark.parametrize("body", [{}, {"on": "false"}, {"on": 1}, {"on": None}, {"on": []}, {"on": False, "pin": 17}, []])
def test_invalid_lamp_commands(client, command_headers, body):
    assert client.post("/api/lamp", json=body, headers=command_headers).status_code == 400
    assert client.get("/api/status").json["lamp"]["on"] is False


@pytest.mark.parametrize("body", [
    {}, {"mode": "invalid"}, {"mode": None}, {"on_time": "24:00"}, {"off_time": "7:00"},
    {"on_time": "20:00"}, {"on_time": 800}, {"relay_pin": 18}, {"on_time": "08:00\n"},
    {"off_time": "12:60"}, {"mode": ["auto"]},
])
def test_invalid_settings_do_not_change_state(client, command_headers, body):
    before = client.get("/api/status").json["lamp"]
    assert client.put("/api/settings", json=body, headers=command_headers).status_code == 400
    after = client.get("/api/status").json["lamp"]
    assert after["mode"] == before["mode"]
    assert after["schedule"] == before["schedule"]


def test_saving_schedule_in_manual_preserves_manual_state(client, command_headers):
    client.post("/api/lamp", json={"on": True}, headers=command_headers)
    response = client.put("/api/settings", json={"on_time": "22:00", "off_time": "06:00"}, headers=command_headers)
    assert response.status_code == 200
    assert response.json["lamp"]["on"] is True
    assert response.json["lamp"]["schedule"]["overnight"] is True


def test_json_errors_and_payload_limit(client, command_headers):
    assert client.post("/api/lamp", data="{", content_type="application/json", headers=command_headers).status_code == 400
    response = client.post("/api/lamp", data='{"on":true,"padding":"' + "a" * 5000 + '"}', content_type="application/json", headers=command_headers)
    assert response.status_code == 413
    assert client.get("/api/missing").status_code == 404
    assert client.get("/health").json == {"status": "ok"}
