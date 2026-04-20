"""Manual PAO -> AIE official-info query runner."""

from __future__ import annotations

import argparse
import json
from typing import Any

from admitpilot.app import build_application
from admitpilot.config import load_settings
from admitpilot.core.schemas import UserProfile
from admitpilot.pao.contracts import OrchestrationRequest


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        default="",
        help="Natural-language official-info query routed through PAO.",
    )
    parser.add_argument(
        "--cycle",
        default=settings.default_cycle,
        help="Admissions cycle used in orchestration constraints.",
    )
    parser.add_argument(
        "--timezone",
        default=settings.timezone,
        help="Timezone used in orchestration constraints.",
    )
    parser.add_argument(
        "--show-records",
        action="store_true",
        help="Print the full AIE official_records payload.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    application = build_application(settings=settings)
    if args.query.strip():
        _run_query(
            application=application,
            query=args.query.strip(),
            cycle=args.cycle,
            timezone=args.timezone,
            show_records=args.show_records,
        )
        return
    _interactive_loop(
        application=application,
        cycle=args.cycle,
        timezone=args.timezone,
        show_records=args.show_records,
    )


def _interactive_loop(
    application: Any,
    cycle: str,
    timezone: str,
    show_records: bool,
) -> None:
    print("PAO -> AIE 官网信息查询已启动。")
    print("直接输入问题，输入 exit / quit / q 结束。")
    print()
    while True:
        try:
            query = input("Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("已退出。")
            return
        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            print("已退出。")
            return
        print()
        _run_query(
            application=application,
            query=query,
            cycle=cycle,
            timezone=timezone,
            show_records=show_records,
        )
        print()


def _run_query(
    application: Any,
    query: str,
    cycle: str,
    timezone: str,
    show_records: bool,
) -> None:
    response = application.orchestrator.invoke(
        OrchestrationRequest(
            user_query=query,
            profile=UserProfile(),
            constraints={"cycle": cycle, "timezone": timezone},
        )
    )
    print("=== Query ===")
    print(query)
    print()
    print("=== PAO Summary ===")
    print(response.summary)
    print()
    print("=== Agent Results ===")
    print([f"{item.agent}:{item.task}:{item.status.value}" for item in response.results])
    print()
    context = response.context
    if context is None or "aie" not in context.shared_memory:
        raise SystemExit("AIE output not found in shared_memory.")
    aie_output = context.shared_memory["aie"]
    print("=== AIE Routing Scope ===")
    print(
        json.dumps(
            {
                "target_schools": aie_output.get("target_schools", []),
                "target_program": aie_output.get("target_program", ""),
                "target_program_by_school": aie_output.get("target_program_by_school", {}),
                "unsupported_program_by_school": aie_output.get(
                    "unsupported_program_by_school", {}
                ),
                "official_source_urls_by_school": aie_output.get(
                    "official_source_urls_by_school", {}
                ),
                "official_status_by_school": aie_output.get("official_status_by_school", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print()
    print("=== AIE Extracted Official Fields ===")
    print(
        json.dumps(
            _compact_official_records(aie_output.get("official_records", [])),
            ensure_ascii=False,
            indent=2,
        )
    )
    if show_records:
        print()
        print("=== Full official_records ===")
        print(json.dumps(aie_output.get("official_records", []), ensure_ascii=False, indent=2))


def _compact_official_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in records:
        compact.append(
            {
                "school": item.get("school", ""),
                "program": item.get("program", ""),
                "page_type": item.get("page_type", ""),
                "source_url": item.get("source_url", ""),
                "effective_date": item.get("effective_date", ""),
                "confidence": item.get("confidence", 0.0),
                "parse_confidence": item.get("parse_confidence", 0.0),
                "changed_fields": item.get("changed_fields", ""),
                "extracted_fields": item.get("extracted_fields", {}),
            }
        )
    return compact


if __name__ == "__main__":
    main()
