"""Bootstrap case library from community-observed signals."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from admitpilot.debug.library_validation import validate_case_record

OUTPUT_PATH = Path("data/case_library/case_library.json")


@dataclass(frozen=True)
class CaseSeed:
    school: str
    program: str
    source_url: str
    summary: str
    outcome: str
    confidence: float
    credibility_label: str
    source_site_score: float
    evidence_completeness: float
    cross_source_consistency: float
    freshness_score: float


CASE_SEEDS: tuple[CaseSeed, ...] = (
    CaseSeed(
        school="NUS",
        program="MCOMP_CS",
        source_url="https://forums.hardwarezone.com.sg/threads/nus-master-of-computing-application.6307786/",
        summary="Forum posts indicate local applicants with strong honors and referrals report positive admit outcomes.",
        outcome="offer",
        confidence=0.64,
        credibility_label="medium",
        source_site_score=0.62,
        evidence_completeness=0.58,
        cross_source_consistency=0.57,
        freshness_score=0.52,
    ),
    CaseSeed(
        school="NUS",
        program="MCOMP_CS",
        source_url="https://www.hotcoursesabroad.com/india/forum/thread/profile-evaluation-for-mcomp-is-specialization-from-nus-msis-from-ntu/22068",
        summary="Profile review post shows GRE 314 and work experience; community feedback marks case as borderline for NUS MComp.",
        outcome="pending_or_reject_risk",
        confidence=0.55,
        credibility_label="low",
        source_site_score=0.56,
        evidence_completeness=0.48,
        cross_source_consistency=0.5,
        freshness_score=0.46,
    ),
    CaseSeed(
        school="HKU",
        program="MSCS",
        source_url="https://bbs.gter.net/thread-2242934-1-1.html",
        summary="Forum participants describe written test plus interview; stronger algorithm fundamentals correlate with admits.",
        outcome="offer",
        confidence=0.6,
        credibility_label="medium",
        source_site_score=0.58,
        evidence_completeness=0.55,
        cross_source_consistency=0.56,
        freshness_score=0.51,
    ),
    CaseSeed(
        school="HKU",
        program="MSCS",
        source_url="https://offer.1point3acres.com/program/hku-ms-in-computer-science-4672/discuss",
        summary="Aggregated applicant threads suggest offers are concentrated in early rounds with complete documents.",
        outcome="offer",
        confidence=0.62,
        credibility_label="medium",
        source_site_score=0.6,
        evidence_completeness=0.57,
        cross_source_consistency=0.59,
        freshness_score=0.55,
    ),
    CaseSeed(
        school="CUHK",
        program="MSCS",
        source_url="https://msc.cse.cuhk.edu.hk/?lang=en&page_id=65",
        summary="Official FAQ release window November to May used as proxy baseline for offer timeline monitoring.",
        outcome="timeline_signal_only",
        confidence=0.68,
        credibility_label="medium",
        source_site_score=0.74,
        evidence_completeness=0.63,
        cross_source_consistency=0.66,
        freshness_score=0.64,
    ),
    CaseSeed(
        school="HKUST",
        program="MSIT",
        source_url="https://offer.1point3acres.com/program/hkust-msc-in-information-technology-2020/",
        summary="Community aggregate reports average GPA 3.77 and GRE 326 with strong offer share in sampled data.",
        outcome="offer",
        confidence=0.66,
        credibility_label="medium",
        source_site_score=0.61,
        evidence_completeness=0.59,
        cross_source_consistency=0.61,
        freshness_score=0.5,
    ),
    CaseSeed(
        school="HKUST",
        program="MSIT",
        source_url="https://offer.1point3acres.com/program/2020",
        summary="Cross-thread observations indicate earlier round submissions produce higher interview conversion.",
        outcome="offer",
        confidence=0.61,
        credibility_label="medium",
        source_site_score=0.59,
        evidence_completeness=0.54,
        cross_source_consistency=0.56,
        freshness_score=0.48,
    ),
    CaseSeed(
        school="NTU",
        program="MSAI",
        source_url="https://www.ntu.edu.sg/computing/admissions/graduate-programmes/master-of-science-programmes/frequently-asked-questions",
        summary="FAQ timeline and document checklist used as high-confidence baseline where community offer posts are sparse.",
        outcome="timeline_signal_only",
        confidence=0.7,
        credibility_label="high",
        source_site_score=0.8,
        evidence_completeness=0.67,
        cross_source_consistency=0.69,
        freshness_score=0.66,
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh case library JSON.")
    parser.add_argument("--cycle", default=str(date.today().year), help="Target admissions cycle")
    args = parser.parse_args()
    cycle = str(args.cycle)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    records = [_build_record(seed=seed, cycle=cycle, now=now, idx=idx) for idx, seed in enumerate(CASE_SEEDS)]

    validation_errors: list[dict[str, Any]] = []
    for record in records:
        issues = validate_case_record(record)
        if issues:
            validation_errors.append(
                {
                    "candidate_fingerprint": record["candidate_fingerprint"],
                    "school": record["school"],
                    "issues": issues,
                }
            )

    payload = {
        "cycle": cycle,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "records": records,
        "validation": {
            "record_count": len(records),
            "invalid_count": len(validation_errors),
            "errors": validation_errors,
        },
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {OUTPUT_PATH}")
    print(f"case records: {len(records)}")
    print(f"invalid records: {len(validation_errors)}")
    if validation_errors:
        print("validation errors detected:")
        for item in validation_errors:
            print(f"- {item['candidate_fingerprint']}: {'; '.join(item['issues'])}")


def _build_record(seed: CaseSeed, cycle: str, now: datetime, idx: int) -> dict[str, Any]:
    raw_key = f"{seed.school}|{seed.program}|{seed.source_url}|{idx}"
    fingerprint_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:12]
    return {
        "candidate_fingerprint": f"anon-{fingerprint_hash}",
        "school": seed.school,
        "program": seed.program,
        "cycle": cycle,
        "source_type": "community",
        "source_url": seed.source_url,
        "background_summary": seed.summary,
        "outcome": seed.outcome,
        "captured_at": now.isoformat().replace("+00:00", "Z"),
        "source_site_score": seed.source_site_score,
        "evidence_completeness": seed.evidence_completeness,
        "cross_source_consistency": seed.cross_source_consistency,
        "freshness_score": seed.freshness_score,
        "confidence": seed.confidence,
        "credibility_label": seed.credibility_label,
    }


if __name__ == "__main__":
    main()
