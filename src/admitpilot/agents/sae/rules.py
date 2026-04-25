"""Program rule loading and validation for SAE."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True)
class ProgramRule:
    school: str
    program: str
    hard_thresholds: dict[str, float]
    soft_thresholds: dict[str, float]
    recommended_backgrounds: list[str]
    risk_flags: list[str]
    missing_input_penalties: dict[str, float]

    @property
    def key(self) -> str:
        return f"{self.school}:{self.program}"


class RuleLoadError(ValueError):
    """Raised when a rules file is malformed."""


def load_program_rules(rules_dir: Path) -> dict[str, ProgramRule]:
    """Load all YAML rules from directory keyed by school+program."""
    loaded: dict[str, ProgramRule] = {}
    for path in sorted(rules_dir.glob("*.yaml")):
        payload = _read_yaml(path)
        rule = _parse_rule(path=path, payload=payload)
        loaded[rule.key] = rule
    return loaded


def _read_yaml(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuleLoadError(f"{path}: top-level YAML must be mapping")
    return parsed


def _parse_rule(path: Path, payload: dict[str, Any]) -> ProgramRule:
    required_fields = {
        "school",
        "program",
        "hard_thresholds",
        "soft_thresholds",
        "recommended_backgrounds",
        "risk_flags",
        "missing_input_penalties",
    }
    missing = sorted(required_fields - set(payload))
    if missing:
        raise RuleLoadError(f"{path}: missing required fields: {', '.join(missing)}")
    school = _required_text(path, payload, "school")
    program = _required_text(path, payload, "program")
    hard_thresholds = _score_map(path, payload, "hard_thresholds")
    soft_thresholds = _score_map(path, payload, "soft_thresholds")
    recommended_backgrounds = _string_list(path, payload, "recommended_backgrounds")
    risk_flags = _string_list(path, payload, "risk_flags")
    missing_input_penalties = _score_map(path, payload, "missing_input_penalties")
    return ProgramRule(
        school=school,
        program=program,
        hard_thresholds=hard_thresholds,
        soft_thresholds=soft_thresholds,
        recommended_backgrounds=recommended_backgrounds,
        risk_flags=risk_flags,
        missing_input_penalties=missing_input_penalties,
    )


def _required_text(path: Path, payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise RuleLoadError(f"{path}: {field_name} must be non-empty string")
    return value.strip().upper() if field_name == "school" else value.strip()


def _string_list(path: Path, payload: dict[str, Any], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuleLoadError(f"{path}: {field_name} must be list[str]")
    return [item.strip() for item in value if item.strip()]


def _score_map(path: Path, payload: dict[str, Any], field_name: str) -> dict[str, float]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise RuleLoadError(f"{path}: {field_name} must be mapping")
    normalized: dict[str, float] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise RuleLoadError(f"{path}: {field_name} keys must be string")
        if not isinstance(item, (int, float)):
            raise RuleLoadError(f"{path}: {field_name}.{key} must be number")
        numeric = float(item)
        if numeric < 0:
            raise RuleLoadError(f"{path}: {field_name}.{key} must be >= 0")
        normalized[key] = numeric
    return normalized
