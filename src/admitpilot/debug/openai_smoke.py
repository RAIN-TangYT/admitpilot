from __future__ import annotations

import argparse

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.config import load_settings
from admitpilot.core.schemas import AgentTask, ApplicationContext, UserProfile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="ping", type=str)
    args = parser.parse_args()
    settings = load_settings()
    agent = AIEAgent(service=AdmissionsIntelligenceService())
    task = AgentTask(
        name="llm_smoke_test",
        description="OpenAI connectivity smoke test",
        agent="aie",
        payload={"prompt": args.prompt},
    )
    context = ApplicationContext(user_query=args.prompt, profile=UserProfile())
    result = agent.run(task=task, context=context)
    if not settings.openai_api_key.strip():
        raise RuntimeError("OpenAI API key is not configured in the current settings.")
    print(result.output.get("content", ""))


if __name__ == "__main__":
    main()
