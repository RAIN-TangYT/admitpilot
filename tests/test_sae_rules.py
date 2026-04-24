from pathlib import Path
from unittest.mock import patch

import pytest

from admitpilot.agents.sae.rules import RuleLoadError, load_program_rules


def test_load_program_rules_from_repo_data() -> None:
    rules_dir = Path(__file__).resolve().parents[1] / "data" / "program_rules"
    rules = load_program_rules(rules_dir)
    assert "NUS:MCOMP_CS" in rules
    assert "NTU:MSAI" in rules
    assert rules["HKU:MSCS"].hard_thresholds["gpa_min"] >= 3.0


def test_load_program_rules_rejects_missing_fields() -> None:
    broken = Path("broken.yaml")
    payloads = {
        broken: "school: NUS\nprogram: MCOMP_CS\nhard_thresholds:\n  gpa_min: 3.4\n",
    }
    with patch.object(Path, "glob", return_value=[broken]), patch.object(
        Path,
        "read_text",
        autospec=True,
        side_effect=lambda self, encoding="utf-8": payloads[self],
    ):
        with pytest.raises(RuleLoadError):
            load_program_rules(Path("unused"))


def test_load_program_rules_rejects_invalid_score_type() -> None:
    broken = Path("broken.yaml")
    payloads = {
        broken: "\n".join(
            [
                "school: NUS",
                "program: MCOMP_CS",
                "hard_thresholds:",
                "  gpa_min: high",
                "soft_thresholds:",
                "  gpa_target: 3.7",
                "recommended_backgrounds:",
                "  - computer science",
                "risk_flags:",
                "  - heavy_competition",
                "missing_input_penalties:",
                "  ielts: 0.06",
            ]
        ),
    }
    with patch.object(Path, "glob", return_value=[broken]), patch.object(
        Path,
        "read_text",
        autospec=True,
        side_effect=lambda self, encoding="utf-8": payloads[self],
    ):
        with pytest.raises(RuleLoadError):
            load_program_rules(Path("unused"))
