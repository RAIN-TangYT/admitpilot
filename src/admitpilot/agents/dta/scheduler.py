"""Milestone graph scheduler with dependency validation."""

from __future__ import annotations

from collections import defaultdict, deque

from admitpilot.agents.dta.schemas import Milestone


class MissingDependencyError(ValueError):
    """Raised when a milestone depends on an unknown key."""


class CyclicDependencyError(ValueError):
    """Raised when milestone dependencies contain a cycle."""


def schedule_milestones(milestones: list[Milestone]) -> list[Milestone]:
    """Return topologically sorted milestones; validate missing/cyclic deps."""
    by_key = {item.key: item for item in milestones}
    for item in milestones:
        for dependency in item.depends_on:
            if dependency not in by_key:
                raise MissingDependencyError(
                    f"milestone={item.key} depends_on missing key={dependency}"
                )

    in_degree: dict[str, int] = {item.key: 0 for item in milestones}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for item in milestones:
        for dependency in item.depends_on:
            in_degree[item.key] += 1
            outgoing[dependency].append(item.key)

    queue: deque[str] = deque(
        sorted([key for key, degree in in_degree.items() if degree == 0], key=str)
    )
    ordered_keys: list[str] = []
    while queue:
        current = queue.popleft()
        ordered_keys.append(current)
        for downstream in sorted(outgoing[current]):
            in_degree[downstream] -= 1
            if in_degree[downstream] == 0:
                queue.append(downstream)

    if len(ordered_keys) != len(milestones):
        unresolved = sorted(set(in_degree) - set(ordered_keys))
        raise CyclicDependencyError(f"cyclic dependencies found: {','.join(unresolved)}")

    return [by_key[key] for key in ordered_keys]
