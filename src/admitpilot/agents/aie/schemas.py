"""AIE 结构化输出模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


@dataclass
class OfficialAdmissionRecord:
    """官网招生记录。"""

    school: str
    program: str
    cycle: str
    page_type: str
    source_url: str
    content: str
    published_date: date
    effective_date: date
    fetched_at: datetime
    source_hash: str
    quality_score: float
    confidence: float
    source_type: str = "official"
    source_credibility: str = "official_primary"
    version_id: str = ""
    is_policy_change: bool = False
    change_type: str = "updated"
    delta_summary: str = ""


@dataclass
class CaseRecord:
    """第三方案例记录。"""

    candidate_fingerprint: str
    school: str
    program: str
    cycle: str
    source_type: str
    source_url: str
    background_summary: str
    outcome: str
    captured_at: datetime
    source_site_score: float
    evidence_completeness: float
    cross_source_consistency: float
    freshness_score: float
    confidence: float
    credibility_label: str = "medium"


@dataclass
class CaseSnapshot:
    """案例快照统计。"""

    snapshot_date: date
    sample_size: int
    patterns: list[str] = field(default_factory=list)
    confidence_distribution: dict[str, int] = field(default_factory=dict)
    expires_at: datetime | None = None


@dataclass
class OfficialCycleSnapshot:
    """当前申请季官方信息快照。"""

    school: str
    program: str
    cycle: str
    as_of_date: date
    status: Literal["official_found", "predicted", "mixed"]
    confidence: float
    is_predicted: bool
    entries: list[OfficialAdmissionRecord] = field(default_factory=list)
    prediction_basis: list[str] = field(default_factory=list)
    update_released: bool = False
    expires_at: datetime | None = None


@dataclass
class ForecastSignal:
    """当前申请季信息不足时的预测信号。"""

    school: str
    insight: str
    confidence: float
    basis: str
    reason: str = ""


@dataclass
class AdmissionsIntelligencePack:
    """AIE 标准化情报包。"""

    official_long_memory: list[OfficialAdmissionRecord] = field(default_factory=list)
    case_long_memory: list[CaseRecord] = field(default_factory=list)
    official_cycle_snapshots: list[OfficialCycleSnapshot] = field(default_factory=list)
    case_snapshot: CaseSnapshot | None = None
    forecast_signals: list[ForecastSignal] = field(default_factory=list)
    official_status_by_school: dict[str, str] = field(default_factory=dict)
    cache_hit_count: int = 0
