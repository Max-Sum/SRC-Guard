from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class ActivePlay:
    client: str
    expires_at: datetime
    updated_at: datetime

    @property
    def mode(self) -> str:
        return "playing"

    @property
    def block_until(self) -> datetime:
        return self.expires_at


class PlayState:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = RLock()
        self._plays: dict[str, ActivePlay] = {}
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._plays = {}
                return
            raw = json.loads(self.path.read_text())
            plays = raw.get("plays", {})
            self._plays = {
                client: ActivePlay(
                    client=client,
                    expires_at=parse_ts(data["expires_at"]),
                    updated_at=parse_ts(data["updated_at"]),
                )
                for client, data in plays.items()
            }

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data: dict[str, Any] = {
                "plays": {
                    client: {
                        "expires_at": play.expires_at.isoformat(),
                        "updated_at": play.updated_at.isoformat(),
                    }
                    for client, play in sorted(self._plays.items())
                }
            }
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
            tmp.replace(self.path)

    def prune(self, now: datetime | None = None) -> None:
        now = now or utc_now()
        with self._lock:
            before = len(self._plays)
            self._plays = {
                client: play
                for client, play in self._plays.items()
                if play.block_until > now
            }
            if len(self._plays) != before:
                self.save()

    def start(self, client: str, expires_at: datetime) -> ActivePlay:
        now = utc_now()
        with self._lock:
            play = ActivePlay(client=client, expires_at=expires_at, updated_at=now)
            self._plays[client] = play
            self.save()
            return play

    def stop(self, client: str) -> bool:
        with self._lock:
            removed = self._plays.pop(client, None) is not None
            if removed:
                self.save()
            return removed

    def active(self, now: datetime | None = None) -> list[ActivePlay]:
        with self._lock:
            self.prune(now)
            return sorted(self._plays.values(), key=lambda play: play.block_until)

    def is_blocked(self, now: datetime | None = None) -> bool:
        return bool(self.active(now))
