from pathlib import Path

import pytest

from admitpilot.agents.aie.fetchers import (
    DisallowedDomainError,
    FixtureHttpClient,
    OfficialPageFetcher,
    OfficialPageSpec,
)
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "official_pages"


def test_official_fetcher_reads_local_fixture_with_metadata() -> None:
    catalog = DEFAULT_ADMISSIONS_CATALOG
    url = catalog.build_page_url("HKUST", "MSCS", "2026", "requirements")
    fetcher = OfficialPageFetcher(
        http_client=FixtureHttpClient(
            {url: FIXTURE_ROOT / "hkust_mscs_2026_requirements.html"}
        ),
        mode="fixture",
    )
    spec = OfficialPageSpec(
        school="HKUST",
        program="MSCS",
        cycle="2026",
        page_type="requirements",
        url=url,
        allowed_domains=catalog.official_domains("HKUST"),
    )

    page = fetcher.fetch(spec)

    assert page.spec.school == "HKUST"
    assert page.status_code == 200
    assert page.mode == "fixture"
    assert "HKUST MSCS 2026 Entry Requirements" in page.content


def test_official_fetcher_rejects_non_whitelisted_domain() -> None:
    fetcher = OfficialPageFetcher(http_client=FixtureHttpClient({}), mode="fixture")
    spec = OfficialPageSpec(
        school="HKUST",
        program="MSCS",
        cycle="2026",
        page_type="requirements",
        url="https://malicious.example.com/mscs.html",
        allowed_domains=DEFAULT_ADMISSIONS_CATALOG.official_domains("HKUST"),
    )

    with pytest.raises(DisallowedDomainError):
        fetcher.fetch(spec)
