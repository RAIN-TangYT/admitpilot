from pathlib import Path
from uuid import uuid4

import pytest

from admitpilot.config import load_settings

_ENV_KEYS = (
    "ADMITPILOT_RUN_MODE",
    "ADMITPILOT_TIMEZONE",
    "ADMITPILOT_LOG_LEVEL",
    "ADMITPILOT_DEFAULT_CYCLE",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
    "OPENAI_TIMEOUT_SECONDS",
    "ADMITPILOT_DATABASE_URL",
    "ADMITPILOT_REDIS_URL",
    "ADMITPILOT_OBJECT_STORE_ENDPOINT",
    "ADMITPILOT_OBJECT_STORE_BUCKET",
    "ADMITPILOT_OBJECT_STORE_ACCESS_KEY",
    "ADMITPILOT_OBJECT_STORE_SECRET_KEY",
    "ADMITPILOT_OFFICIAL_LIBRARY_PATH",
    "ADMITPILOT_API_HOST",
    "ADMITPILOT_API_PORT",
)


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _workspace_env_file() -> Path:
    temp_dir = Path.cwd() / ".pytest-local"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir / f"settings-{uuid4().hex}.env"


def test_load_settings_uses_defaults_when_env_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    env_file = _workspace_env_file()
    try:
        env_file.write_text("", encoding="utf-8")
        settings = load_settings(env_file=env_file)

        assert settings.run_mode == "demo"
        assert settings.timezone == "Asia/Shanghai"
        assert settings.default_cycle == "2026"
        assert settings.openai_model == "gpt-5.4-nano"
        assert settings.official_library_path == "data/official_library/official_library.json"
        assert settings.api_port == 8000
    finally:
        env_file.unlink(missing_ok=True)


def test_load_settings_prefers_environment_over_env_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_env(monkeypatch)
    env_file = _workspace_env_file()
    try:
        env_file.write_text(
            "\n".join(
                [
                    "ADMITPILOT_RUN_MODE=demo",
                    "OPENAI_MODEL=file-model",
                    "ADMITPILOT_API_PORT=8100",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("ADMITPILOT_RUN_MODE", "test")
        monkeypatch.setenv("OPENAI_MODEL", "env-model")
        monkeypatch.setenv("ADMITPILOT_API_PORT", "8200")

        settings = load_settings(env_file=env_file)

        assert settings.run_mode == "test"
        assert settings.openai_model == "env-model"
        assert settings.api_port == 8200
    finally:
        env_file.unlink(missing_ok=True)


def test_load_settings_requires_database_url_for_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)

    with pytest.raises(ValueError, match="database_url is required for staging/prod"):
        load_settings(overrides={"ADMITPILOT_RUN_MODE": "prod"})
