from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SRC_GUARD_")

    token: str
    src_container: str = "starrailcopilot-src-1"
    default_play_minutes: int = 120
    max_play_minutes: int = 720
    auto_resume: bool = True
    state_file: str = "/data/state.json"
