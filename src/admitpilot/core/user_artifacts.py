"""Structured user evidence entities for CDS fact grounding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, cast

EvidenceType = Literal[
    "course",
    "project",
    "internship",
    "research",
    "award",
    "language",
    "referee",
]
_ALLOWED_EVIDENCE_TYPES = {
    "course",
    "project",
    "internship",
    "research",
    "award",
    "language",
    "referee",
}


@dataclass
class EvidenceArtifact:
    """Base evidence unit submitted by user."""

    artifact_id: str
    title: str
    source_ref: str
    evidence_type: EvidenceType
    date_range: str = ""
    details: str = ""
    verified: bool = False

    def mark_verified(self) -> None:
        self.verified = True


@dataclass
class UserArtifactsBundle:
    """All user evidence grouped by type."""

    artifacts: list[EvidenceArtifact] = field(default_factory=list)

    def add(self, artifact: EvidenceArtifact) -> None:
        self.artifacts.append(artifact)

    def of_type(self, evidence_type: EvidenceType) -> list[EvidenceArtifact]:
        return [item for item in self.artifacts if item.evidence_type == evidence_type]

    def unverified(self) -> list[EvidenceArtifact]:
        return [item for item in self.artifacts if not item.verified]


def parse_user_artifacts(payload: list[dict[str, str | bool]]) -> UserArtifactsBundle:
    """Parse dict payload into typed artifacts with minimal validation."""
    bundle = UserArtifactsBundle()
    for raw in payload:
        artifact_id = str(raw.get("artifact_id", "")).strip()
        title = str(raw.get("title", "")).strip()
        source_ref = str(raw.get("source_ref", "")).strip()
        evidence_type = str(raw.get("evidence_type", "")).strip()
        if not artifact_id or not title or not source_ref or not evidence_type:
            raise ValueError("artifact_id/title/source_ref/evidence_type are required")
        if evidence_type not in _ALLOWED_EVIDENCE_TYPES:
            raise ValueError(f"unsupported evidence_type: {evidence_type}")
        bundle.add(
            EvidenceArtifact(
                artifact_id=artifact_id,
                title=title,
                source_ref=source_ref,
                evidence_type=cast(EvidenceType, evidence_type),
                date_range=str(raw.get("date_range", "")),
                details=str(raw.get("details", "")),
                verified=bool(raw.get("verified", False)),
            )
        )
    return bundle
