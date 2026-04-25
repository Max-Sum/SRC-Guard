from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SRC_GUARD_TOKEN", "test-token")
    monkeypatch.setenv("SRC_GUARD_STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setenv("SRC_GUARD_AUTO_RESUME", "true")

    import app.main as main

    class FakeDocker:
        def __init__(self):
            self.calls = []
            self.game_result = "stopped"

        def force_stop_games(self):
            self.calls.append("games")
            return self.game_result

        def stop_src(self):
            self.calls.append("stop")
            return "stopped"

        def start_src(self):
            self.calls.append("start")
            return "started"

    fake_docker = FakeDocker()
    main.settings.token = "test-token"
    main.settings.state_file = str(tmp_path / "state.json")
    main.state = main.PlayState(main.settings.state_file)
    main.docker_control = fake_docker
    return TestClient(main.app), fake_docker, main


def auth():
    return {"Authorization": "Bearer test-token"}


def test_start_refreshes_same_client_and_stops_src(tmp_path, monkeypatch):
    client, fake_docker, _ = make_client(tmp_path, monkeypatch)

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
    assert fake_docker.calls == ["games", "stop", "games", "stop"]


def test_start_still_stops_src_when_force_stop_games_fails(tmp_path, monkeypatch):
    client, fake_docker, _ = make_client(tmp_path, monkeypatch)
    fake_docker.game_result = "error"

    response = client.post(
        "/webhook/play/start",
        json={"client": "ipad", "minutes": 30},
        headers=auth(),
    )

    assert response.status_code == 200
    assert response.json()["game"] == "error"
    assert response.json()["docker"] == "stopped"
    assert fake_docker.calls == ["games", "stop"]


def test_start_still_stops_src_when_src_container_is_not_running(tmp_path, monkeypatch):
    client, fake_docker, _ = make_client(tmp_path, monkeypatch)
    fake_docker.game_result = "skipped_container_not_running"

    response = client.post(
        "/webhook/play/start",
        json={"client": "ipad", "minutes": 30},
        headers=auth(),
    )

    assert response.status_code == 200
    assert response.json()["blocked"] is True
    assert response.json()["game"] == "skipped_container_not_running"
    assert response.json()["docker"] == "stopped"
    assert fake_docker.calls == ["games", "stop"]


def test_allow_start_is_locked_while_external_play_is_active(tmp_path, monkeypatch):
    client, _, _ = make_client(tmp_path, monkeypatch)

    client.post(
        "/webhook/play/start",
        json={"client": "phone", "minutes": 30},
        headers=auth(),
    )

    response = client.get("/allow-start", headers=auth())

    assert response.status_code == 423
    assert response.json()["allowed"] is False


def test_stop_only_resumes_when_last_client_stops(tmp_path, monkeypatch):
    client, fake_docker, _ = make_client(tmp_path, monkeypatch)

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
    assert fake_docker.calls == ["games", "stop", "games", "stop", "start"]


def test_expired_sessions_no_longer_block(tmp_path, monkeypatch):
    client, _, main = make_client(tmp_path, monkeypatch)

    play = main.state.start("ipad", main.utc_now() - timedelta(minutes=1))
    assert play.client == "ipad"

    response = client.get("/allow-start", headers=auth())

    assert response.status_code == 200
    assert response.json()["allowed"] is True


def test_parse_adb_devices_returns_only_ready_devices():
    from app.docker_control import parse_adb_devices

    output = (
        b"List of devices attached\n"
        b"emulator-5554\tdevice\n"
        b"192.168.1.2:5555\toffline\n"
        b"abc123\tunauthorized\n"
        b"device-two\tdevice product:test\n"
    )

    assert parse_adb_devices(output) == ["emulator-5554", "device-two"]


def test_docker_control_force_stops_all_games_on_all_adb_devices(monkeypatch):
    import app.docker_control as docker_control

    class FakeContainer:
        status = "running"

        def __init__(self):
            self.commands = []

        def reload(self):
            return None

        def exec_run(self, command):
            self.commands.append(command)
            if command == ["adb", "devices"]:
                output = b"List of devices attached\nserial-a\tdevice\nserial-b\tdevice\n"
                return SimpleNamespace(exit_code=0, output=output)
            return SimpleNamespace(exit_code=0, output=b"")

    container = FakeContainer()
    client = SimpleNamespace(
        containers=SimpleNamespace(get=lambda name: container)
    )
    monkeypatch.setattr(docker_control.docker, "from_env", lambda: client)

    control = docker_control.DockerControl("starrailcopilot-src-1")

    assert control.force_stop_games() == "stopped"
    assert container.commands[0] == ["adb", "devices"]
    assert container.commands[1:] == [
        ["adb", "-s", device, "shell", "am", "force-stop", package]
        for device in ["serial-a", "serial-b"]
        for package in docker_control.GAME_PACKAGES
    ]


def test_docker_control_reports_no_adb_devices(monkeypatch):
    import app.docker_control as docker_control

    class FakeContainer:
        status = "running"

        def reload(self):
            return None

        def exec_run(self, command):
            assert command == ["adb", "devices"]
            return SimpleNamespace(exit_code=0, output=b"List of devices attached\n")

    client = SimpleNamespace(
        containers=SimpleNamespace(get=lambda name: FakeContainer())
    )
    monkeypatch.setattr(docker_control.docker, "from_env", lambda: client)

    control = docker_control.DockerControl("starrailcopilot-src-1")

    assert control.force_stop_games() == "no_devices"
