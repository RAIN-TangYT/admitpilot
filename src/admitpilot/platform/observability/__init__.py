"""可观测性公共组件。"""

from admitpilot.platform.observability.contracts import (
    InMemoryMetricSink,
    InMemoryTraceSink,
    MetricPoint,
    MetricSink,
    ObservabilitySuite,
    TraceRecord,
    TraceSink,
    build_default_observability_suite,
)

__all__ = [
    "TraceRecord",
    "MetricPoint",
    "TraceSink",
    "MetricSink",
    "InMemoryTraceSink",
    "InMemoryMetricSink",
    "ObservabilitySuite",
    "build_default_observability_suite",
]
