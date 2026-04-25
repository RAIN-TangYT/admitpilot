"""Trace and metric contracts for orchestration runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from admitpilot.platform.common.time import to_iso_utc


@dataclass
class TraceCollector:
    """Collect structured trace spans."""

    _spans: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def start_span(self, name: str, trace_id: str, attrs: dict[str, Any] | None = None) -> None:
        self._spans.append(
            {
                "event": "span_start",
                "name": name,
                "trace_id": trace_id,
                "attrs": attrs or {},
                "at": to_iso_utc(),
            }
        )

    def end_span(self, name: str, trace_id: str, attrs: dict[str, Any] | None = None) -> None:
        self._spans.append(
            {
                "event": "span_end",
                "name": name,
                "trace_id": trace_id,
                "attrs": attrs or {},
                "at": to_iso_utc(),
            }
        )

    def spans(self) -> list[dict[str, Any]]:
        return list(self._spans)


@dataclass
class MetricsCollector:
    """Collect counters in-memory."""

    counters: dict[str, int] = field(default_factory=dict)

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value


__all__ = ["MetricsCollector", "TraceCollector"]
