from pathlib import Path

import pytest

from admitpilot.agents.sae.rules import RuleLoadError, load_program_rules


def test_load_program_rules_from_repo_data() -> None:
    rules_dir = Path(__file__).resolve().parents[1] / "data" / "program_rules"
    rules = load_program_rules(rules_dir)
    assert "NUS:MCOMP_CS" in rules
    assert "NTU:MSAI" in rules
    assert rules["HKU:MSCS"].hard_thresholds["gpa_min"] >= 3.0


def test_load_program_rules_rejects_missing_fields(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "school: NUS\nprogram: MCOMP_CS\nhard_thresholds:\n  gpa_min: 3.4\n",
        encoding="utf-8",
    )
    with pytest.raises(RuleLoadError):
        load_program_rules(tmp_path)


def test_load_program_rules_rejects_invalid_score_type(tmp_path: Path) -> None:
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "\n".join(
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
        encoding="utf-8",
    )
    with pytest.raises(RuleLoadError):
        load_program_rules(tmp_path)
