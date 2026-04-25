from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

from app.docker_control import DockerControl
from app.settings import Settings
from app.state import PlayState, utc_now


settings = Settings()
state = PlayState(settings.state_file)
docker_control = DockerControl(settings.src_container)
app = FastAPI(title="SRC Guard", version="1.0.0")


class PlayStartRequest(BaseModel):
    client: str = Field(min_length=1, max_length=64)
    duration: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_duration_fields(cls, data: object) -> object:
        if isinstance(data, dict) and "duration" not in data:
            if "lock_duration_minutes" in data:
                data = {**data, "duration": data["lock_duration_minutes"]}
            elif "minutes" in data:
                data = {**data, "duration": data["minutes"]}
        return data


class PlayStopRequest(BaseModel):
    client: str = Field(min_length=1, max_length=64)


def require_token(
    authorization: Optional[str] = Header(default=None),
    x_src_guard_token: Optional[str] = Header(default=None),
) -> None:
    bearer = f"Bearer {settings.token}"
    if authorization == bearer or x_src_guard_token == settings.token:
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def clamp_duration(requested_duration: int | None) -> int:
    value = requested_duration or settings.default_duration
    return min(value, settings.max_duration)


def active_payload() -> list[dict[str, str | None]]:
    return [
        {
            "client": play.client,
            "mode": play.mode,
            "expires_at": play.expires_at.isoformat(),
            "block_until": play.block_until.isoformat(),
            "updated_at": play.updated_at.isoformat(),
        }
        for play in state.active()
    ]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status", dependencies=[Depends(require_token)])
def get_status() -> dict[str, object]:
    active = active_payload()
    return {"blocked": bool(active), "active": active}


@app.post("/webhook/play/start", dependencies=[Depends(require_token)])
def play_start(request: PlayStartRequest) -> dict[str, object]:
    expires_at = utc_now() + timedelta(minutes=clamp_duration(request.duration))
    was_blocked = state.is_blocked()

    play = state.start(request.client, expires_at)
    if was_blocked:
        game_result = "skipped_already_blocked"
        docker_result = "skipped_already_blocked"
    else:
        game_result = docker_control.force_stop_games()
        docker_result = docker_control.stop_src()

    return {
        "blocked": True,
        "client": play.client,
        "expires_at": play.expires_at.isoformat(),
        "extended": was_blocked,
        "game": game_result,
        "docker": docker_result,
        "active": active_payload(),
    }


@app.post("/webhook/play/stop", dependencies=[Depends(require_token)])
def play_stop(request: PlayStopRequest) -> dict[str, object]:
    removed = state.stop(request.client)
    blocked = state.is_blocked()
    docker_result = "skipped"
    if removed and not blocked and settings.auto_resume:
        docker_result = docker_control.start_src()

    return {
        "accepted": removed,
        "removed": removed,
        "blocked": blocked,
        "docker": docker_result,
        "active": active_payload(),
    }


@app.get("/allow-start", dependencies=[Depends(require_token)])
def allow_start(response: Response) -> dict[str, object]:
    blocked = state.is_blocked()
    response.status_code = status.HTTP_423_LOCKED if blocked else status.HTTP_200_OK
    return {"allowed": not blocked, "blocked": blocked, "active": active_payload()}
