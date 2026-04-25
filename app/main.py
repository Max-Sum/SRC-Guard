from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.adb_control import AdbControl
from app.docker_control import DockerControl
from app.settings import Settings
from app.state import PlayState, utc_now


settings = Settings()
state = PlayState(settings.state_file)
adb_control = AdbControl(settings.game_package, settings.adb_connect)
docker_control = DockerControl(settings.src_container)
app = FastAPI(title="SRC Guard", version="1.0.0")


class PlayStartRequest(BaseModel):
    client: str = Field(min_length=1, max_length=64)
    minutes: Optional[int] = Field(default=None, ge=1)


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


def active_payload() -> list[dict[str, str]]:
    return [
        {
            "client": play.client,
            "expires_at": play.expires_at.isoformat(),
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
    minutes = request.minutes or settings.default_play_minutes
    minutes = min(minutes, settings.max_play_minutes)
    expires_at = utc_now() + timedelta(minutes=minutes)

    play = state.start(request.client, expires_at)
    game_result = adb_control.force_stop_game()
    docker_result = docker_control.stop_src()

    return {
        "blocked": True,
        "client": play.client,
        "expires_at": play.expires_at.isoformat(),
        "game": game_result,
        "docker": docker_result,
        "active": active_payload(),
    }


@app.post("/webhook/play/stop", dependencies=[Depends(require_token)])
def play_stop(request: PlayStopRequest) -> dict[str, object]:
    removed = state.stop(request.client)
    blocked = state.is_blocked()
    docker_result = "skipped"
    if not blocked and settings.auto_resume:
        docker_result = docker_control.start_src()

    return {
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
