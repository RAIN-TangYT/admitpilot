"""可观测性接口与初始化定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(slots=True)
class TraceRecord:
    """Trace 记录。"""

    trace_id: str
    span_id: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class MetricPoint:
    """指标点。"""

    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TraceSink(Protocol):
    """Trace 写入接口。"""

    def write(self, record: TraceRecord) -> None:
        """写入 trace 记录。"""

    def list_by_trace(self, trace_id: str) -> list[TraceRecord]:
        """按 trace 查询。"""


class MetricSink(Protocol):
    """指标写入接口。"""

    def write(self, point: MetricPoint) -> None:
        """写入指标。"""

    def list_by_name(self, name: str) -> list[MetricPoint]:
        """按名称查询指标。"""


@dataclass(slots=True)
class InMemoryTraceSink:
    """内存 trace sink。"""

    records: list[TraceRecord] = field(default_factory=list)

    def write(self, record: TraceRecord) -> None:
        self.records.append(record)

    def list_by_trace(self, trace_id: str) -> list[TraceRecord]:
        return [item for item in self.records if item.trace_id == trace_id]


@dataclass(slots=True)
class InMemoryMetricSink:
    """内存 metrics sink。"""

    points: list[MetricPoint] = field(default_factory=list)

    def write(self, point: MetricPoint) -> None:
        self.points.append(point)

    def list_by_name(self, name: str) -> list[MetricPoint]:
        return [item for item in self.points if item.name == name]


@dataclass(slots=True)
class ObservabilitySuite:
    """可观测初始化集合。"""

    trace_sink: TraceSink
    metric_sink: MetricSink
    todo: tuple[str, ...] = field(
        default_factory=lambda: (
            "接入 OpenTelemetry 导出",
            "接入 Prometheus 指标聚合",
            "接入告警阈值策略",
        )
    )


def build_default_observability_suite() -> ObservabilitySuite:
    return ObservabilitySuite(
        trace_sink=InMemoryTraceSink(),
        metric_sink=InMemoryMetricSink(),
    )
