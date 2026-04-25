from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class AdbControl:
    def __init__(self, game_package: str, adb_connect: Optional[str] = None):
        self.game_package = game_package
        self.adb_connect = adb_connect

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )

    def force_stop_game(self) -> str:
        try:
            adb_command = ["adb"]
            if self.adb_connect:
                connect = self._run(["adb", "connect", self.adb_connect])
                if connect.returncode != 0:
                    logger.warning(
                        "Failed to connect adb target %s: %s",
                        self.adb_connect,
                        connect.stderr.strip() or connect.stdout.strip(),
                    )
                    return "connect_error"
                adb_command.extend(["-s", self.adb_connect])

            result = self._run(
                adb_command + ["shell", "am", "force-stop", self.game_package]
            )
            if result.returncode == 0:
                return "stopped"

            logger.warning(
                "Failed to force-stop game package %s: %s",
                self.game_package,
                result.stderr.strip() or result.stdout.strip(),
            )
            return "error"
        except FileNotFoundError:
            logger.exception("adb executable was not found")
            return "adb_not_found"
        except subprocess.TimeoutExpired:
            logger.exception(
                "Timed out while force-stopping game package %s", self.game_package
            )
            return "timeout"
