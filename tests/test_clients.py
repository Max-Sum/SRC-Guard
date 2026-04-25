import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_CLIENT = ROOT / "clients" / "android-tasker" / "src-guard-tasker.sh"
WINDOWS_CLIENT = ROOT / "clients" / "windows" / "SRCGuardClient.ps1"
WINDOWS_INSTALLER = ROOT / "clients" / "windows" / "Install-ScheduledTasks.ps1"


def client_env(tmp_path, *, hold_seconds=0):
    config = tmp_path / "src-guard-tasker.env"
    state_dir = tmp_path / "state"
    config.write_text(
        "\n".join(
            [
                'GUARD_URL="http://guard.local:22368"',
                'TOKEN="test-token"',
                'CLIENT="Test Phone"',
                'DURATION="360"',
                f'HOLD_SECONDS="{hold_seconds}"',
            ]
        )
        + "\n"
    )
    env = os.environ.copy()
    env.update(
        {
            "SRC_GUARD_CONFIG": str(config),
            "SRC_GUARD_DRY_RUN": "1",
            "STATE_DIR": str(state_dir),
        }
    )
    return env, state_dir


def run_android_client(tmp_path, action, *, hold_seconds=0, extra_env=None):
    env, state_dir = client_env(tmp_path, hold_seconds=hold_seconds)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ["sh", str(ANDROID_CLIENT), action],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result, state_dir


def test_android_tasker_client_start_refresh_and_hold_stop(tmp_path):
    start, state_dir = run_android_client(tmp_path, "start")
    assert "POST http://guard.local:22368/webhook/play/start" in start.stdout
    assert '"duration":360' in start.stdout
    assert "lock_duration" not in start.stdout
    assert '"minutes"' not in start.stdout
    assert (state_dir / "mode").read_text().strip() == "playing"

    refresh, _ = run_android_client(tmp_path, "refresh-if-active")
    assert "POST http://guard.local:22368/webhook/play/start" in refresh.stdout

    stop, _ = run_android_client(
        tmp_path,
        "hold-stop",
        extra_env={"SRC_GUARD_FOREGROUND_HOLD": "1"},
    )
    assert "POST http://guard.local:22368/webhook/play/stop" in stop.stdout
    assert '"interrupt_seconds"' not in stop.stdout
    assert '{"client":"Test Phone"}' in stop.stdout
    assert not (state_dir / "mode").exists()
    assert not (state_dir / "generation").exists()


def test_android_tasker_client_start_cancels_pending_hold_stop(tmp_path):
    env, state_dir = client_env(tmp_path, hold_seconds=1)
    subprocess.run(
        ["sh", str(ANDROID_CLIENT), "start"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    hold_env = env.copy()
    hold_env["SRC_GUARD_FOREGROUND_HOLD"] = "1"
    hold = subprocess.Popen(
        ["sh", str(ANDROID_CLIENT), "hold-stop"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=hold_env,
    )
    time.sleep(0.1)

    subprocess.run(
        ["sh", str(ANDROID_CLIENT), "start"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    stdout, stderr = hold.communicate(timeout=5)

    assert hold.returncode == 0, stderr
    assert "pending stop was cancelled" in stdout
    assert (state_dir / "mode").read_text().strip() == "playing"


def test_windows_client_uses_process_event_triggers_without_hold_or_launching_game():
    client = WINDOWS_CLIENT.read_text()
    installer = WINDOWS_INSTALLER.read_text()
    android_client = ANDROID_CLIENT.read_text()

    assert '"event-start"' in client
    assert '"event-stop"' in client
    assert "/webhook/play/refresh" not in client
    assert '"monitor"' not in client
    assert '"hold-stop"' not in client
    assert "GameProcessName" in client
    assert "GameProcessPath" in client
    assert "COMPUTERNAME" in client
    assert "windows-pc" not in client
    assert "duration" in client
    assert "LockDuration" not in client
    assert "PlayMinutes" not in client
    assert "Start-Process" not in client

    assert 'Name = "SRC Guard Game Start"' in installer
    assert 'Name = "SRC Guard Game Stop"' in installer
    assert 'Action = "event-start"' in installer
    assert 'Action = "event-stop"' in installer
    assert 'TriggerType = "ProcessStart"' in installer
    assert 'TriggerType = "ProcessStop"' in installer
    assert "4688" in installer
    assert "4689" in installer
    assert "EnableProcessAudit" in installer
    assert "COMPUTERNAME" in installer
    assert 'GameProcessNames = $GameProcessName' in installer
    assert 'Action = "hold-stop"' not in installer
    assert "detect_client_name" in android_client
    assert "android-phone" not in android_client
