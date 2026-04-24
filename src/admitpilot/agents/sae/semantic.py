"""Pluggable semantic matching for SAE (fake for tests, embedding stub for future)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from admitpilot.core.schemas import UserProfile


@dataclass(frozen=True)
class SemanticMatchResult:
    """Deterministic semantic layer output."""

    score: float
    breakdown: dict[str, Any]


class SemanticMatcher(Protocol):
    """Match user profile text to a school/program signal."""

    def match(self, user_profile: UserProfile, school: str, program: str) -> SemanticMatchResult:
        ...


class FakeSemanticMatcher:
    """Token-overlap heuristic; stable for the same inputs (tests)."""

    _KEYWORDS = ("cs", "ai", "data", "system", "research")

    def match(self, user_profile: UserProfile, school: str, program: str) -> SemanticMatchResult:
        profile_signal = (
            f"{user_profile.major_interest} {' '.join(user_profile.experiences)}".lower()
        )
        school_signal = f"{school} {program}".lower()
        matched = [token for token in self._KEYWORDS if token in profile_signal]
        overlap = len(matched)
        school_bias = 0.05 if "hku" in school_signal else 0.0
        score = max(0.25, min(0.9, 0.35 + overlap * 0.08 + school_bias))
        breakdown: dict[str, Any] = {
            "method": "fake_token_overlap",
            "matched_keywords": matched,
            "overlap_count": overlap,
            "school_bias": school_bias,
        }
        return SemanticMatchResult(score=score, breakdown=breakdown)


class EmbeddingSemanticMatcher:
    """Placeholder for future embedding / LLM semantic similarity (offline tests do not use)."""

    def match(self, user_profile: UserProfile, school: str, program: str) -> SemanticMatchResult:
        del user_profile, school, program
        raise NotImplementedError(
            "EmbeddingSemanticMatcher is not wired; use FakeSemanticMatcher or inject a custom matcher."
        )


def build_semantic_matcher(kind: Literal["fake", "embedding"] = "fake") -> SemanticMatcher:
    if kind == "fake":
        return FakeSemanticMatcher()
    if kind == "embedding":
        return EmbeddingSemanticMatcher()
    raise ValueError(f"unknown semantic matcher kind: {kind}")
