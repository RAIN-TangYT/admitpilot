from dataclasses import dataclass, field
from datetime import date
from typing import Any, cast

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.schemas import AdmissionsIntelligencePack, OfficialCycleSnapshot
from admitpilot.core.schemas import AgentTask, ApplicationContext, UserProfile
from admitpilot.domain.catalog import DEFAULT_ADMISSIONS_CATALOG, AdmissionsCatalog


@dataclass(slots=True)
class _StubAIEService:
    catalog: AdmissionsCatalog = DEFAULT_ADMISSIONS_CATALOG
    calls: list[tuple[tuple[str, ...], str]] = field(default_factory=list)

    def retrieve(
        self,
        query: str,
        cycle: str,
        schools: list[str] | None = None,
        program: str = "",
        as_of_date: date | None = None,
        include_case_updates: bool = True,
    ) -> AdmissionsIntelligencePack:
        del query, cycle, as_of_date, include_case_updates
        self.calls.append((tuple(schools or []), program))
        school = (schools or ["NUS"])[0]
        return AdmissionsIntelligencePack(
            official_cycle_snapshots=[
                OfficialCycleSnapshot(
                    school=school,
                    program=program,
                    cycle="2026",
                    as_of_date=date(2026, 4, 20),
                    status="official_found",
                    confidence=0.8,
                    is_predicted=False,
                )
            ],
            official_status_by_school={school: "official_found"},
        )


def test_aie_agent_uses_program_mapping_per_school() -> None:
    service = _StubAIEService()
    agent = AIEAgent(service=cast(Any, service))
    task = AgentTask(
        name="collect_intelligence",
        agent="aie",
        description="collect intelligence",
        payload={},
    )
    context = ApplicationContext(
        user_query="demo",
        profile=UserProfile(
            target_schools=["NUS", "HKUST"],
            target_programs=["MCOMP_CS", "MSIT"],
        ),
        constraints={
            "cycle": "2026",
            "target_schools": ["NUS", "HKUST"],
            "target_program_by_school": {"NUS": "MCOMP_CS", "HKUST": "MSIT"},
        },
    )

    result = agent.run(task=task, context=context)

    assert service.calls == [(("NUS",), "MCOMP_CS"), (("HKUST",), "MSIT")]
    assert result.output["target_program_by_school"] == {"NUS": "MCOMP_CS", "HKUST": "MSIT"}
    assert result.output["target_program"] == "MULTI_PROGRAM_PORTFOLIO"
