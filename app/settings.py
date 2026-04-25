from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SRC_GUARD_")

    token: str
    src_container: str = "starrailcopilot-src-1"
    default_duration: int = Field(
        360,
        validation_alias=AliasChoices(
            "SRC_GUARD_DEFAULT_DURATION",
            "SRC_GUARD_DEFAULT_LOCK_DURATION_MINUTES",
            "SRC_GUARD_DEFAULT_PLAY_MINUTES",
        ),
    )
    max_duration: int = Field(
        720,
        validation_alias=AliasChoices(
            "SRC_GUARD_MAX_DURATION",
            "SRC_GUARD_MAX_LOCK_DURATION_MINUTES",
            "SRC_GUARD_MAX_PLAY_MINUTES",
        ),
    )
    auto_resume: bool = True
    state_file: str = "/data/state.json"
