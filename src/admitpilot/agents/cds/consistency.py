"""Cross-document consistency checker for CDS drafts."""

from __future__ import annotations

from admitpilot.agents.cds.schemas import ConsistencyIssue, DocumentDraft


def check_consistency(drafts: list[DocumentDraft]) -> list[ConsistencyIssue]:
    """Run deterministic consistency checks across generated drafts."""
    issues: list[ConsistencyIssue] = []
    if not drafts:
        return issues

    if _has_unverified_or_inferred_slots(drafts):
        issues.append(
            ConsistencyIssue(
                severity="medium",
                message="Some fact slots are inferred or missing and require verification.",
                impacted_documents=[
                    f"{item.document_type}:{item.target_school}" for item in drafts
                ],
            )
        )

    timeline_values = _slot_values(drafts, "execution_proof")
    if len(timeline_values) > 1:
        issues.append(
            ConsistencyIssue(
                severity="high",
                message="execution_proof conflicts across documents.",
                impacted_documents=[
                    f"{item.document_type}:{item.target_school}" for item in drafts
                ],
            )
        )

    motivation_values = _slot_values(drafts, "motivation_core")
    if len(motivation_values) > 1:
        issues.append(
            ConsistencyIssue(
                severity="high",
                message="motivation_core conflicts across documents.",
                impacted_documents=[
                    f"{item.document_type}:{item.target_school}" for item in drafts
                ],
            )
        )

    school_name_issues = _check_school_name_alignment(drafts)
    issues.extend(school_name_issues)
    return issues


def _has_unverified_or_inferred_slots(drafts: list[DocumentDraft]) -> bool:
    return any(
        slot.status in ("missing", "inferred")
        for draft in drafts
        for slot in draft.fact_slots
    )


def _slot_values(drafts: list[DocumentDraft], slot_id: str) -> set[str]:
    values: set[str] = set()
    for draft in drafts:
        for slot in draft.fact_slots:
            if slot.slot_id == slot_id and slot.value:
                values.add(slot.value)
    return values


def _check_school_name_alignment(drafts: list[DocumentDraft]) -> list[ConsistencyIssue]:
    issues: list[ConsistencyIssue] = []
    for draft in drafts:
        if draft.document_type != "sop":
            continue
        if not draft.target_school:
            continue
        if not any(draft.target_school in item for item in draft.content_outline):
            issues.append(
                ConsistencyIssue(
                    severity="medium",
                    message=(
                        f"{draft.document_type}:{draft.target_school} does not mention "
                        "the target school name."
                    ),
                    impacted_documents=[f"{draft.document_type}:{draft.target_school}"],
                )
            )
    return issues
