from __future__ import annotations

import logging

import docker
from docker.errors import DockerException, NotFound

logger = logging.getLogger(__name__)


class DockerControl:
    def __init__(self, src_container: str):
        self.src_container = src_container

    def _container(self):
        client = docker.from_env()
        return client.containers.get(self.src_container)

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
