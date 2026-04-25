from admitpilot.core.user_artifacts import EvidenceArtifact, parse_user_artifacts


def test_parse_user_artifacts_success() -> None:
    bundle = parse_user_artifacts(
        [
            {
                "artifact_id": "proj-1",
                "title": "Distributed Systems Project",
                "source_ref": "cv:project-1",
                "evidence_type": "project",
                "date_range": "2024-09~2024-12",
                "details": "Capstone",
                "verified": True,
            },
            {
                "artifact_id": "lang-1",
                "title": "IELTS 7.5",
                "source_ref": "cert:ielts",
                "evidence_type": "language",
                "verified": False,
            },
        ]
    )
    assert len(bundle.artifacts) == 2
    assert bundle.of_type("project")[0].verified is True
    assert bundle.unverified()[0].evidence_type == "language"


def test_parse_user_artifacts_rejects_missing_required_fields() -> None:
    invalid_payload: list[dict[str, str | bool]] = [{"artifact_id": "x", "title": "bad"}]
    try:
        parse_user_artifacts(invalid_payload)
    except ValueError:
        return
    raise AssertionError("expected ValueError for missing required fields")


def test_evidence_artifact_mark_verified() -> None:
    artifact = EvidenceArtifact(
        artifact_id="res-1",
        title="Research Assistant",
        source_ref="proof:offer-letter",
        evidence_type="research",
    )
    assert artifact.verified is False
    artifact.mark_verified()
    assert artifact.verified is True
