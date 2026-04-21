"""Refresh official library with field validation and anti-bot fallbacks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from admitpilot.debug.library_validation import (
    is_predicted_official_record,
    validate_official_record,
)

OUTPUT_PATH = Path("data/official_library/official_library.json")

USER_AGENTS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_0) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
)


@dataclass(frozen=True)
class OfficialTarget:
    school: str
    program: str
    page_type: str
    primary_url: str
    fallback_url: str | None = None
    fallback_summary: str | None = None


TARGETS: tuple[OfficialTarget, ...] = (
    OfficialTarget(
        school="NUS",
        program="MCOMP_CS",
        page_type="application",
        primary_url="https://www.comp.nus.edu.sg/programmes/pg/mcs/application/",
        fallback_summary=(
            "NUS MComp CS application window for Aug 2026 intake opens on 2025-10-01 and closes "
            "on 2026-01-31; fee SGD109; outcome by end-May; TOEFL/IELTS required for non-English "
            "instruction backgrounds."
        ),
    ),
    OfficialTarget(
        school="NTU",
        program="MSAI",
        page_type="admissions",
        primary_url="https://www.ntu.edu.sg/education/graduate-programme/master-of-science-in-artificial-intelligence",
        fallback_summary=(
            "NTU MSAI requires good CS-related degree (or degree plus 2-year experience), TOEFL "
            "iBT>=100 or IELTS>=6.5, and full document set in online application portal."
        ),
    ),
    OfficialTarget(
        school="HKU",
        program="MSCS",
        page_type="procedures",
        primary_url="https://www.msc-cs.hku.hk/Admission/Procedures",
        fallback_summary=(
            "HKU MSc CS main round deadline is 2025-12-01 and clearing round deadline is "
            "2026-04-30 (HKT noon); application fee HKD600; submit transcripts, degree proof, "
            "language proof, CV, and identity documents via TPg admission system."
        ),
    ),
    OfficialTarget(
        school="CUHK",
        program="MSCS",
        page_type="deadline",
        primary_url="https://msc.cse.cuhk.edu.hk/?lang=en&page_id=90",
        fallback_summary=(
            "CUHK MSc CS application period starts in September and 2026 deadline is "
            "2026-01-31."
        ),
    ),
    OfficialTarget(
        school="HKUST",
        program="MSIT",
        page_type="admissions",
        primary_url="https://seng.hkust.edu.hk/academics/taught-postgraduate/msc-it",
        fallback_summary=(
            "HKUST MSc IT 2026/27 rounds are 2025-11-01, 2026-01-01, 2026-03-01; requires "
            "CS-related bachelor degree and English proficiency per HKUST Graduate School."
        ),
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh official library JSON.")
    parser.add_argument("--cycle", default=str(date.today().year), help="Target admissions cycle")
    args = parser.parse_args()
    cycle = str(args.cycle)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    records: list[dict[str, Any]] = []
    school_status: list[dict[str, str | bool]] = []
    validation_errors: list[dict[str, Any]] = []
    phase_logs: list[str] = []
    phase_logs.append("phase=discover targets=5")

    for target in TARGETS:
        fetch_result = _fetch_official_content(target)
        phase_logs.append(
            "phase=fetch "
            f"school={target.school} fetched={fetch_result['fetched']} "
            f"fallback_resolved={fetch_result['fallback_resolved']} "
            f"url={fetch_result['source_url']}"
        )
        record = _build_record(target=target, cycle=cycle, now=now, fetch_result=fetch_result)
        issues = validate_official_record(record)
        if issues:
            validation_errors.append({"school": target.school, "issues": issues})
        predicted = is_predicted_official_record(record)
        status = "predicted" if predicted else "official_found"
        school_status.append(
            {
                "school": target.school,
                "program": target.program,
                "status": status,
                "is_predicted": predicted,
                "source_url": str(record["source_url"]),
            }
        )
        records.append(record)

    payload = {
        "cycle": cycle,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "phase_logs": phase_logs,
        "records": records,
        "school_status": school_status,
        "validation": {
            "record_count": len(records),
            "predicted_count": sum(1 for item in records if is_predicted_official_record(item)),
            "invalid_count": len(validation_errors),
            "errors": validation_errors,
        },
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {OUTPUT_PATH}")
    print(f"official records: {len(records)}")
    print(f"predicted records: {payload['validation']['predicted_count']}")
    print(f"invalid records: {len(validation_errors)}")
    if validation_errors:
        print("validation errors detected:")
        for item in validation_errors:
            print(f"- {item['school']}: {'; '.join(item['issues'])}")


def _build_record(
    target: OfficialTarget, cycle: str, now: datetime, fetch_result: dict[str, Any]
) -> dict[str, Any]:
    content = str(fetch_result["content"])
    source_type = "official"
    source_credibility = "official_primary"
    quality_score = 0.92
    confidence = 0.88
    change_type = "updated"
    if fetch_result["fallback_resolved"]:
        source_type = "official_fallback"
        source_credibility = "official_secondary"
        quality_score = 0.76
        confidence = 0.74
    if not fetch_result["fetched"] and not fetch_result["fallback_resolved"]:
        source_type = "predicted"
        source_credibility = "anti_bot_fallback"
        quality_score = 0.58
        confidence = 0.62
        change_type = "predicted"
    published_date = _infer_published_date(cycle=cycle, content=content)
    source_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]
    version_id = f"{target.school}-{cycle}-{target.page_type}-{source_hash[:8]}"
    return {
        "school": target.school,
        "program": target.program,
        "cycle": cycle,
        "page_type": target.page_type,
        "source_url": str(fetch_result["source_url"]),
        "content": content,
        "published_date": published_date,
        "effective_date": published_date,
        "fetched_at": now.isoformat().replace("+00:00", "Z"),
        "source_hash": source_hash,
        "quality_score": quality_score,
        "confidence": confidence,
        "source_type": source_type,
        "source_credibility": source_credibility,
        "version_id": version_id,
        "is_policy_change": "update" in content.lower() or "deadline" in content.lower(),
        "change_type": change_type,
        "delta_summary": _build_delta_summary(
            content=content,
            fetched=bool(fetch_result["fetched"]),
            fallback_resolved=bool(fetch_result["fallback_resolved"]),
        ),
    }


def _fetch_official_content(target: OfficialTarget) -> dict[str, Any]:
    urls = [target.primary_url]
    if target.fallback_url:
        urls.append(target.fallback_url)
    for url in urls:
        for user_agent in USER_AGENTS:
            try:
                text = _fetch_url(url=url, user_agent=user_agent)
                return {
                    "fetched": True,
                    "fallback_resolved": False,
                    "source_url": url,
                    "content": _clean_text(text),
                }
            except (HTTPError, URLError, TimeoutError):
                continue
    if target.fallback_summary:
        return {
            "fetched": False,
            "fallback_resolved": True,
            "source_url": target.primary_url,
            "content": target.fallback_summary,
        }
    return {
        "fetched": False,
        "fallback_resolved": False,
        "source_url": target.primary_url,
        "content": f"{target.school} {target.program} {target.page_type} page is anti-bot protected; keep predicted.",
    }


def _fetch_url(url: str, user_agent: str) -> str:
    request = Request(
        url=url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310
        body = response.read()
    return body.decode("utf-8", errors="ignore")


def _clean_text(raw_html: str) -> str:
    stripped = re.sub(r"<script[\s\S]*?</script>", " ", raw_html, flags=re.IGNORECASE)
    stripped = re.sub(r"<style[\s\S]*?</style>", " ", stripped, flags=re.IGNORECASE)
    plain = re.sub(r"<[^>]+>", " ", stripped)
    collapsed = re.sub(r"\s+", " ", plain).strip()
    return collapsed[:1800]


def _infer_published_date(cycle: str, content: str) -> str:
    matches = re.findall(r"(20\d{2})", content)
    if cycle in matches:
        return f"{cycle}-01-01"
    for candidate in matches:
        year = int(candidate)
        if 2020 <= year <= 2100:
            return f"{year}-01-01"
    return f"{cycle}-01-01"


def _build_delta_summary(content: str, fetched: bool, fallback_resolved: bool) -> str:
    lowered = content.lower()
    if fallback_resolved:
        return "anti-bot resolved via manual official summary"
    if not fetched:
        return "anti-bot encountered; pending manual review"
    if "deadline" in lowered:
        return "deadline and application timeline refreshed"
    if "requirement" in lowered:
        return "admission requirements refreshed"
    return "official page snapshot refreshed"


if __name__ == "__main__":
    main()
