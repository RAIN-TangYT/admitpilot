from admitpilot.agents.dta.scheduler import (
    CyclicDependencyError,
    MissingDependencyError,
    schedule_milestones,
)
from admitpilot.agents.dta.schemas import Milestone


def test_schedule_milestones_orders_by_dependencies() -> None:
    milestones = [
        Milestone(key="submission_batch_1", title="submit", due_week=6, depends_on=["doc_pack_v1"]),
        Milestone(key="scope_lock", title="scope", due_week=1),
        Milestone(key="doc_pack_v1", title="doc", due_week=3, depends_on=["scope_lock"]),
    ]
    ordered = schedule_milestones(milestones)
    assert [item.key for item in ordered] == ["scope_lock", "doc_pack_v1", "submission_batch_1"]


def test_schedule_milestones_raises_on_missing_dependency() -> None:
    milestones = [Milestone(key="doc_pack_v1", title="doc", due_week=3, depends_on=["missing"])]
    try:
        schedule_milestones(milestones)
    except MissingDependencyError:
        return
    raise AssertionError("expected MissingDependencyError")


def test_schedule_milestones_raises_on_cycle() -> None:
    milestones = [
        Milestone(key="a", title="A", due_week=1, depends_on=["b"]),
        Milestone(key="b", title="B", due_week=2, depends_on=["a"]),
    ]
    try:
        schedule_milestones(milestones)
    except CyclicDependencyError:
        return
    raise AssertionError("expected CyclicDependencyError")
