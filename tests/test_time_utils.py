from datetime import UTC, datetime, timedelta, timezone

from admitpilot.platform.common.time import ensure_utc, to_iso_utc, utc_now, utc_today


def test_utc_now_returns_timezone_aware_datetime() -> None:
    current = utc_now()

    assert current.tzinfo == UTC
    assert utc_today() == current.date()


def test_ensure_utc_normalizes_naive_and_aware_datetimes() -> None:
    naive = datetime(2026, 1, 1, 12, 0, 0)
    aware = datetime(2026, 1, 1, 20, 0, 0, tzinfo=timezone(timedelta(hours=8)))

    assert ensure_utc(naive).tzinfo == UTC
    assert ensure_utc(aware).tzinfo == UTC
    assert ensure_utc(aware).hour == 12


def test_to_iso_utc_serializes_with_utc_offset() -> None:
    rendered = to_iso_utc(datetime(2026, 1, 1, 12, 0, 0))

    assert rendered.endswith("+00:00")
