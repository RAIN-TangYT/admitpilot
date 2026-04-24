"""Application settings loader."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_RUN_MODES = {"demo", "test", "staging", "prod"}
_DEFAULT_OFFICIAL_LIBRARY_PATH = "data/official_library/official_library.json"
_DEFAULT_CASE_LIBRARY_PATH = "data/case_library/case_library.json"
_TEST_RUNTIME_OFFICIAL_LIBRARY_PATH = ".pytest-local/runtime_official_library.test.json"


def _read_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _coerce_int(raw: str | None, default: int) -> int:
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


@dataclass(slots=True, frozen=True)
class AdmitPilotSettings:
    """Single source of truth for runtime configuration."""

    run_mode: str = "demo"
    timezone: str = "Asia/Shanghai"
    log_level: str = "INFO"
    default_cycle: str = "2026"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-nano"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: int = 30
    semantic_matcher_kind: str = ""
    database_url: str = ""
    redis_url: str = ""
    object_store_endpoint: str = ""
    object_store_bucket: str = "admitpilot-artifacts"
    object_store_access_key: str = ""
    object_store_secret_key: str = ""
    official_library_path: str = _DEFAULT_OFFICIAL_LIBRARY_PATH
    case_library_path: str = _DEFAULT_CASE_LIBRARY_PATH
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    def __post_init__(self) -> None:
        normalized_mode = self.run_mode.strip().lower()
        object.__setattr__(self, "run_mode", normalized_mode)
        if normalized_mode not in _RUN_MODES:
            raise ValueError(f"unsupported_run_mode:{self.run_mode}")
        normalized_matcher = self.semantic_matcher_kind.strip().lower()
        if not normalized_matcher:
            normalized_matcher = "fake" if normalized_mode == "test" else "embedding"
        object.__setattr__(self, "semantic_matcher_kind", normalized_matcher)
        if normalized_matcher not in {"fake", "embedding"}:
            raise ValueError(f"unsupported_semantic_matcher_kind:{normalized_matcher}")
        if self.openai_timeout_seconds <= 0:
            raise ValueError("openai_timeout_seconds must be positive")
        if self.api_port <= 0:
            raise ValueError("api_port must be positive")
        if normalized_mode in {"staging", "prod"} and not self.database_url.strip():
            raise ValueError("database_url is required for staging/prod")
        has_access_key = bool(self.object_store_access_key.strip())
        has_secret_key = bool(self.object_store_secret_key.strip())
        if has_access_key != has_secret_key:
            raise ValueError(
                "object_store_access_key and object_store_secret_key must be set together"
            )

    @property
    def is_test_mode(self) -> bool:
        return self.run_mode == "test"

    @property
    def is_demo_mode(self) -> bool:
        return self.run_mode == "demo"

    @property
    def runtime_official_library_path(self) -> str:
        if self.is_test_mode and self.official_library_path == _DEFAULT_OFFICIAL_LIBRARY_PATH:
            return _TEST_RUNTIME_OFFICIAL_LIBRARY_PATH
        return self.official_library_path


def load_settings(
    overrides: Mapping[str, object] | None = None,
    env_file: str | Path | None = None,
) -> AdmitPilotSettings:
    """Load settings from .env, process environment, then explicit overrides."""

    effective_env_file = Path(env_file) if env_file is not None else Path.cwd() / ".env"
    values = _read_env_file(effective_env_file)
    values.update(os.environ)
    if overrides:
        values.update({key: str(value) for key, value in overrides.items()})
    return AdmitPilotSettings(
        run_mode=str(values.get("ADMITPILOT_RUN_MODE", "demo")),
        timezone=str(values.get("ADMITPILOT_TIMEZONE", "Asia/Shanghai")),
        log_level=str(values.get("ADMITPILOT_LOG_LEVEL", "INFO")),
        default_cycle=str(values.get("ADMITPILOT_DEFAULT_CYCLE", "2026")),
        openai_api_key=str(values.get("OPENAI_API_KEY", "")),
        openai_model=str(values.get("OPENAI_MODEL", "gpt-5.4-nano")),
        openai_embedding_model=str(
            values.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        ),
        openai_base_url=str(values.get("OPENAI_BASE_URL", "https://api.openai.com/v1")),
        openai_timeout_seconds=_coerce_int(values.get("OPENAI_TIMEOUT_SECONDS"), 30),
        semantic_matcher_kind=str(values.get("ADMITPILOT_SEMANTIC_MATCHER_KIND", "")),
        database_url=str(values.get("ADMITPILOT_DATABASE_URL", "")),
        redis_url=str(values.get("ADMITPILOT_REDIS_URL", "")),
        object_store_endpoint=str(values.get("ADMITPILOT_OBJECT_STORE_ENDPOINT", "")),
        object_store_bucket=str(
            values.get("ADMITPILOT_OBJECT_STORE_BUCKET", "admitpilot-artifacts")
        ),
        object_store_access_key=str(values.get("ADMITPILOT_OBJECT_STORE_ACCESS_KEY", "")),
        object_store_secret_key=str(values.get("ADMITPILOT_OBJECT_STORE_SECRET_KEY", "")),
        official_library_path=str(
            values.get(
                "ADMITPILOT_OFFICIAL_LIBRARY_PATH",
                _DEFAULT_OFFICIAL_LIBRARY_PATH,
            )
        ),
        case_library_path=str(
            values.get(
                "ADMITPILOT_CASE_LIBRARY_PATH",
                _DEFAULT_CASE_LIBRARY_PATH,
            )
        ),
        api_host=str(values.get("ADMITPILOT_API_HOST", "127.0.0.1")),
        api_port=_coerce_int(values.get("ADMITPILOT_API_PORT"), 8000),
    )
