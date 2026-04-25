from datetime import timedelta
import subprocess

from fastapi.testclient import TestClient


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SRC_GUARD_TOKEN", "test-token")
    monkeypatch.setenv("SRC_GUARD_STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setenv("SRC_GUARD_AUTO_RESUME", "true")
    monkeypatch.setenv("SRC_GUARD_GAME_PACKAGE", "com.miHoYo.hkrpg")

    import app.main as main

    class FakeAdb:
        def __init__(self):
            self.calls = []
            self.game_result = "stopped"

        def force_stop_game(self):
            self.calls.append("game")
            return self.game_result

    class FakeDocker:
        def __init__(self):
            self.calls = []

        def stop_src(self):
            self.calls.append("stop")
            return "stopped"

        def start_src(self):
            self.calls.append("start")
            return "started"

    fake_adb = FakeAdb()
    fake_docker = FakeDocker()
    main.settings.token = "test-token"
    main.settings.state_file = str(tmp_path / "state.json")
    main.state = main.PlayState(main.settings.state_file)
    main.adb_control = fake_adb
    main.docker_control = fake_docker
    return TestClient(main.app), fake_adb, fake_docker, main


def auth():
    return {"Authorization": "Bearer test-token"}


def test_start_refreshes_same_client_and_stops_src(tmp_path, monkeypatch):
    client, fake_adb, fake_docker, _ = make_client(tmp_path, monkeypatch)

    first = client.post(
        "/webhook/play/start",
        json={"client": "ipad", "minutes": 30},
        headers=auth(),
    )
    second = client.post(
        "/webhook/play/start",
        json={"client": "ipad", "minutes": 60},
        headers=auth(),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(second.json()["active"]) == 1
    assert second.json()["game"] == "stopped"
    assert fake_adb.calls == ["game", "game"]
    assert fake_docker.calls == ["stop", "stop"]


def test_start_still_stops_src_when_force_stop_game_fails(tmp_path, monkeypatch):
    client, fake_adb, fake_docker, _ = make_client(tmp_path, monkeypatch)
    fake_adb.game_result = "error"

    response = client.post(
        "/webhook/play/start",
        json={"client": "ipad", "minutes": 30},
        headers=auth(),
    )

    assert response.status_code == 200
    assert response.json()["game"] == "error"
    assert response.json()["docker"] == "stopped"
    assert fake_adb.calls == ["game"]
    assert fake_docker.calls == ["stop"]


def test_start_still_stops_src_when_adb_is_missing(tmp_path, monkeypatch):
    client, fake_adb, fake_docker, _ = make_client(tmp_path, monkeypatch)
    fake_adb.game_result = "adb_not_found"

    response = client.post(
        "/webhook/play/start",
        json={"client": "ipad", "minutes": 30},
        headers=auth(),
    )

    assert response.status_code == 200
    assert response.json()["blocked"] is True
    assert response.json()["game"] == "adb_not_found"
    assert response.json()["docker"] == "stopped"
    assert fake_docker.calls == ["stop"]


def test_allow_start_is_locked_while_external_play_is_active(tmp_path, monkeypatch):
    client, _, _, _ = make_client(tmp_path, monkeypatch)

    client.post(
        "/webhook/play/start",
        json={"client": "phone", "minutes": 30},
        headers=auth(),
    )

    response = client.get("/allow-start", headers=auth())

    assert response.status_code == 423
    assert response.json()["allowed"] is False


def test_stop_only_resumes_when_last_client_stops(tmp_path, monkeypatch):
    client, fake_adb, fake_docker, _ = make_client(tmp_path, monkeypatch)

    client.post("/webhook/play/start", json={"client": "ipad"}, headers=auth())
    client.post("/webhook/play/start", json={"client": "phone"}, headers=auth())
    first_stop = client.post(
        "/webhook/play/stop", json={"client": "ipad"}, headers=auth()
    )
    second_stop = client.post(
        "/webhook/play/stop", json={"client": "phone"}, headers=auth()
    )

    assert first_stop.json()["blocked"] is True
    assert first_stop.json()["docker"] == "skipped"
    assert second_stop.json()["blocked"] is False
    assert second_stop.json()["docker"] == "started"
    assert fake_adb.calls == ["game", "game"]
    assert fake_docker.calls == ["stop", "stop", "start"]


def test_expired_sessions_no_longer_block(tmp_path, monkeypatch):
    client, _, _, main = make_client(tmp_path, monkeypatch)

    play = main.state.start("ipad", main.utc_now() - timedelta(minutes=1))
    assert play.client == "ipad"

    response = client.get("/allow-start", headers=auth())

    assert response.status_code == 200
    assert response.json()["allowed"] is True


def test_adb_control_force_stops_game_with_direct_adb(monkeypatch):
    import app.adb_control as adb_control

    calls = []

    def fake_run(command, capture_output, check, text, timeout):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(adb_control.subprocess, "run", fake_run)

    control = adb_control.AdbControl("com.miHoYo.hkrpg", "adb-host:5555")

    assert control.force_stop_game() == "stopped"
    assert calls == [
        ["adb", "connect", "adb-host:5555"],
        [
            "adb",
            "-s",
            "adb-host:5555",
            "shell",
            "am",
            "force-stop",
            "com.miHoYo.hkrpg",
        ],
    ]


def test_adb_control_reports_connect_error(monkeypatch):
    import app.adb_control as adb_control

    calls = []

    def fake_run(command, capture_output, check, text, timeout):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")

    monkeypatch.setattr(adb_control.subprocess, "run", fake_run)

    control = adb_control.AdbControl("com.miHoYo.hkrpg", "adb-host:5555")

    assert control.force_stop_game() == "connect_error"
    assert calls == [["adb", "connect", "adb-host:5555"]]
