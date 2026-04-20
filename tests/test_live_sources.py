from admitpilot.agents.aie.live_sources import DEFAULT_LIVE_OFFICIAL_SOURCES
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG


def test_live_sources_cover_catalog_program_pairs() -> None:
    live_pairs = {(item.school, item.program) for item in DEFAULT_LIVE_OFFICIAL_SOURCES}
    catalog = DEFAULT_ADMISSIONS_CATALOG

    missing_pairs = {
        (school, program)
        for school in catalog.all_school_codes()
        for program in catalog.supported_programs(school)
        if (school, program) not in live_pairs
    }

    assert missing_pairs == set()
