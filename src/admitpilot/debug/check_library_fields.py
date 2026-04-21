"""Validate current official/case libraries and list predicted rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from admitpilot.debug.library_validation import (
    is_predicted_official_record,
    validate_case_record,
    validate_official_record,
)

OFFICIAL_PATH = Path("data/official_library/official_library.json")
CASE_PATH = Path("data/case_library/case_library.json")


def main() -> None:
    official_payload = _load_json(OFFICIAL_PATH)
    case_payload = _load_json(CASE_PATH)
    _check_official_payload(official_payload)
    _check_case_payload(case_payload)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"[missing] {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[invalid-json] {path}: {exc}")
        return {}


def _check_official_payload(payload: dict[str, Any]) -> None:
    records = payload.get("records")
    if not isinstance(records, list):
        print("[official] missing records array")
        return
    invalid = 0
    predicted_indexes: list[int] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            invalid += 1
            print(f"[official] record[{idx}] is not object")
            continue
        issues = validate_official_record(record)
        if issues:
            invalid += 1
            print(f"[official] record[{idx}] invalid: {'; '.join(issues)}")
        if is_predicted_official_record(record):
            predicted_indexes.append(idx)
    print(
        f"[official] total={len(records)} invalid={invalid} predicted={len(predicted_indexes)}"
    )
    if predicted_indexes:
        print(f"[official] predicted indexes={predicted_indexes}")


def _check_case_payload(payload: dict[str, Any]) -> None:
    records = payload.get("records")
    if not isinstance(records, list):
        print("[case] missing records array")
        return
    invalid = 0
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            invalid += 1
            print(f"[case] record[{idx}] is not object")
            continue
        issues = validate_case_record(record)
        if issues:
            invalid += 1
            print(f"[case] record[{idx}] invalid: {'; '.join(issues)}")
    print(f"[case] total={len(records)} invalid={invalid}")


if __name__ == "__main__":
    main()
