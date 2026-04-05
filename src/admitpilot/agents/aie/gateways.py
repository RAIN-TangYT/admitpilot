"""AIE 外部数据源网关接口。"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Protocol

from admitpilot.agents.aie.schemas import CaseRecord, OfficialAdmissionRecord


class OfficialSourceGateway(Protocol):
    """官方信息源接口。"""

    def has_cycle_release(self, school: str, cycle: str, as_of_date: date) -> bool:
        """判断当前申请季是否已发布可用官方信息。"""

    def fetch_cycle_records(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> list[OfficialAdmissionRecord]:
        """拉取当前申请季官方记录。"""


class CaseSourceGateway(Protocol):
    """案例信息源接口。"""

    def fetch_case_records(
        self, schools: list[str], program: str, cycle: str, as_of_date: date
    ) -> list[CaseRecord]:
        """拉取案例记录。"""


class StubOfficialSourceGateway:
    """默认官方网关桩实现。

    TODO: 接入真实抓取与解析链路（官网/API/FAQ/PDF）。
    """

    def has_cycle_release(self, school: str, cycle: str, as_of_date: date) -> bool:
        return cycle[-1].isdigit() and (int(cycle[-1]) + len(school)) % 3 != 0

    def fetch_cycle_records(
        self, school: str, program: str, cycle: str, query: str, as_of_date: date
    ) -> list[OfficialAdmissionRecord]:
        fetched_at = datetime.now()
        pages = (
            ("admission", "admission", True, "updated"),
            ("requirement", "requirement", False, "updated"),
            ("faq", "faq", True, "new"),
        )
        records: list[OfficialAdmissionRecord] = []
        for page_type, section, changed, change_type in pages:
            content = f"{school} {cycle} {program} {section} 与查询“{query}”相关。"
            source_hash = hashlib.sha256(
                f"{school}|{program}|{cycle}|{page_type}|{content}".encode()
            ).hexdigest()
            records.append(
                OfficialAdmissionRecord(
                    school=school,
                    program=program,
                    cycle=cycle,
                    page_type=page_type,
                    source_url=f"https://www.{school.lower()}.edu/admissions/{program.lower()}",
                    content=content,
                    published_date=as_of_date,
                    effective_date=as_of_date,
                    fetched_at=fetched_at,
                    source_hash=source_hash,
                    quality_score=0.9,
                    confidence=0.9,
                    version_id=f"{school}-{cycle}-{page_type}-{as_of_date.isoformat()}",
                    is_policy_change=changed,
                    change_type=change_type,
                    delta_summary=f"{school} {page_type} 条目于 {as_of_date.isoformat()} 更新",
                )
            )
        return records


class StubCaseSourceGateway:
    """默认案例网关桩实现。

    TODO: 接入清洗后的 case lake 与可信度标注流水线。
    """

    _SOURCE_SCORE = {"agency": 0.72, "forum": 0.55, "xiaohongshu": 0.48}

    def fetch_case_records(
        self, schools: list[str], program: str, cycle: str, as_of_date: date
    ) -> list[CaseRecord]:
        records: list[CaseRecord] = []
        now = datetime.now()
        for school in schools:
            for idx, source_type in enumerate(("agency", "forum", "xiaohongshu"), start=1):
                score = self._SOURCE_SCORE[source_type]
                records.append(
                    CaseRecord(
                        candidate_fingerprint=f"{school}-{idx}",
                        school=school,
                        program=program,
                        cycle=str(max(int(cycle) - idx, 0)),
                        source_type=source_type,
                        source_url=f"https://example.com/{source_type}/{school.lower()}",
                        background_summary="placeholder: GPA/语言/科研实习标签",
                        outcome="admit" if idx == 1 else "unknown",
                        captured_at=now - timedelta(days=idx * 45),
                        source_site_score=score,
                        evidence_completeness=0.65 + idx * 0.08,
                        cross_source_consistency=0.55 + idx * 0.1,
                        freshness_score=0.9 - idx * 0.1,
                        confidence=min(0.8, score + 0.1),
                        credibility_label="high" if idx == 1 else "medium",
                    )
                )
        return records
