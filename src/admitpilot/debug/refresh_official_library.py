"""Refresh live official AIE library without touching case data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from admitpilot.agents.aie.gateways import CatalogOfficialSourceGateway
from admitpilot.agents.aie.live_sources import DEFAULT_LIVE_OFFICIAL_SOURCES
from admitpilot.agents.aie.repositories import JsonOfficialSnapshotRepository
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.config import load_settings
from admitpilot.platform.common.time import utc_today


def parse_args() -> argparse.Namespace:
    settings = load_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycle", default="2026")
    parser.add_argument(
        "--output",
        default=settings.official_library_path,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository = JsonOfficialSnapshotRepository(path=Path(args.output))
    service = AdmissionsIntelligenceService(
        official_gateway=CatalogOfficialSourceGateway(mode="live"),
        official_repository=repository,
    )
    targets = [(item.school, item.program) for item in DEFAULT_LIVE_OFFICIAL_SOURCES]
    snapshots = service.refresh_official_library(
        query="refresh live official admissions sources",
        cycle=args.cycle,
        targets=targets,
        as_of_date=utc_today(),
    )
    print(
        json.dumps(
            [
                {
                    "school": item.school,
                    "program": item.program,
                    "status": item.status,
                    "entries": len(item.entries),
                    "diffs": len(item.diffs),
                    "confidence": round(item.confidence, 4),
                }
                for item in snapshots
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
