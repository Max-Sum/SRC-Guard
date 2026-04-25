from __future__ import annotations

import logging

import docker
from docker.errors import DockerException, NotFound

logger = logging.getLogger(__name__)

GAME_PACKAGES = (
    "com.miHoYo.cloudgames.hkrpg",
    "com.miHoYo.hkrpg",
    "com.HoYoverse.hkrpgoversea",
)


def parse_adb_devices(output: bytes) -> list[str]:
    devices: list[str] = []
    for raw_line in output.decode(errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


class DockerControl:
    def __init__(self, src_container: str):
        self.src_container = src_container

    def _container(self):
        client = docker.from_env()
        return client.containers.get(self.src_container)

    def force_stop_games(self) -> str:
        try:
            container = self._container()
            container.reload()
            if container.status != "running":
                return "skipped_container_not_running"

            devices_result = container.exec_run(["adb", "devices"])
            if devices_result.exit_code != 0:
                logger.warning(
                    "Failed to list adb devices in %s: exit=%s output=%s",
                    self.src_container,
                    devices_result.exit_code,
                    devices_result.output.decode(errors="replace").strip(),
                )
                return "error"

            devices = parse_adb_devices(devices_result.output)
            if not devices:
                return "no_devices"

            failed = False
            for device in devices:
                for package in GAME_PACKAGES:
                    result = container.exec_run(
                        ["adb", "-s", device, "shell", "am", "force-stop", package]
                    )
                    if result.exit_code != 0:
                        failed = True
                        logger.warning(
                            "Failed to force-stop %s on %s in %s: exit=%s output=%s",
                            package,
                            device,
                            self.src_container,
                            result.exit_code,
                            result.output.decode(errors="replace").strip(),
                        )

            return "partial_error" if failed else "stopped"
        except NotFound:
            logger.warning("SRC container %s was not found", self.src_container)
            return "not_found"
        except DockerException:
            logger.exception("Failed to force-stop games through SRC container adb")
            return "error"

    def stop_src(self) -> str:
        try:
            container = self._container()
            container.stop()
            return "stopped"
        except NotFound:
            logger.warning("SRC container %s was not found", self.src_container)
            return "not_found"
        except DockerException:
            logger.exception("Failed to stop SRC container")
            return "error"

    def start_src(self) -> str:
        try:
            container = self._container()
            container.start()
            return "started"
        except NotFound:
            logger.warning("SRC container %s was not found", self.src_container)
            return "not_found"
        except DockerException:
            logger.exception("Failed to start SRC container")
            return "error"
