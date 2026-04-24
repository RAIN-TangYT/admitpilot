"""Pluggable semantic matching for SAE."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from admitpilot.core.schemas import UserProfile
from admitpilot.platform.llm.openai import OpenAIClient


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
            "method": "deterministic_token_overlap",
            "matched_keywords": matched,
            "overlap_count": overlap,
            "school_bias": school_bias,
        }
        return SemanticMatchResult(score=score, breakdown=breakdown)


@dataclass(slots=True)
class EmbeddingSemanticMatcher:
    """Embedding-based matcher with local hashing fallback for offline runtime."""

    llm_client: OpenAIClient | None = None
    embedding_model: str = "text-embedding-3-small"
    local_dimension: int = 64

    _TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
    _PROGRAM_ALIASES = {
        "MCOMP_CS": "master of computing computer science systems software engineering",
        "MSCS": "master of science computer science algorithms systems software engineering",
        "MSAI": "master of science artificial intelligence machine learning data science",
        "MSIT": "master of science information technology systems software engineering",
        "MSBA": "master of science business analytics data analytics machine learning",
        "MDS": "master of data science analytics machine learning statistics",
        "MTECH_AIS": "master of technology artificial intelligence systems computing",
    }

    def match(self, user_profile: UserProfile, school: str, program: str) -> SemanticMatchResult:
        profile_text = self._profile_text(user_profile)
        target_text = self._target_text(school=school, program=program)
        method = "local_hashing_embedding"
        provider = "local"
        try:
            left_vec, right_vec = self._remote_or_local_vectors(profile_text, target_text)
            if self.llm_client is not None and self.llm_client.enabled:
                method = "openai_embedding_cosine"
                provider = "openai"
        except RuntimeError:
            left_vec = self._hash_vector(profile_text)
            right_vec = self._hash_vector(target_text)
        cosine = self._cosine_similarity(left_vec, right_vec)
        score = round(max(0.25, min(0.9, 0.25 + max(cosine, 0.0) * 0.65)), 4)
        breakdown: dict[str, Any] = {
            "method": method,
            "provider": provider,
            "cosine_similarity": round(cosine, 4),
            "profile_terms": self._tokenize(profile_text)[:6],
            "target_terms": self._tokenize(target_text)[:6],
        }
        return SemanticMatchResult(score=score, breakdown=breakdown)

    def _remote_or_local_vectors(
        self,
        profile_text: str,
        target_text: str,
    ) -> tuple[list[float], list[float]]:
        if self.llm_client is None or not self.llm_client.enabled:
            return self._hash_vector(profile_text), self._hash_vector(target_text)
        vectors = self.llm_client.embed_texts(
            [profile_text, target_text],
            model=self.embedding_model,
        )
        if len(vectors) != 2:
            raise RuntimeError("semantic embedding request returned unexpected vector count")
        return vectors[0], vectors[1]

    def _profile_text(self, user_profile: UserProfile) -> str:
        parts = [
            user_profile.major_interest,
            " ".join(user_profile.experiences),
            " ".join(str(item) for item in user_profile.target_programs),
            " ".join(str(item) for item in user_profile.target_schools),
        ]
        return " ".join(part.strip() for part in parts if part.strip())

    def _target_text(self, school: str, program: str) -> str:
        alias = self._PROGRAM_ALIASES.get(program.upper(), program.replace("_", " "))
        return f"{school} {program} {alias}"

    def _tokenize(self, text: str) -> list[str]:
        return self._TOKEN_PATTERN.findall(text.lower())

    def _hash_vector(self, text: str) -> list[float]:
        vector = [0.0] * self.local_dimension
        for token in self._tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.local_dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return vector

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        dot = sum(l_value * r_value for l_value, r_value in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)


def build_semantic_matcher(
    kind: Literal["fake", "embedding"] = "fake",
    *,
    llm_client: OpenAIClient | None = None,
    embedding_model: str = "text-embedding-3-small",
) -> SemanticMatcher:
    if kind == "fake":
        return FakeSemanticMatcher()
    if kind == "embedding":
        return EmbeddingSemanticMatcher(
            llm_client=llm_client,
            embedding_model=embedding_model,
        )
    raise ValueError(f"unknown semantic matcher kind: {kind}")
