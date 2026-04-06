from __future__ import annotations

import argparse
import os
from pathlib import Path

from admitpilot.agents.aie.agent import AIEAgent
from admitpilot.agents.aie.service import AdmissionsIntelligenceService
from admitpilot.core.schemas import AgentTask, ApplicationContext, UserProfile


def _load_dotenv_if_present() -> None:
    dotenv_path = Path.cwd() / ".env"
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="ping", type=str)
    args = parser.parse_args()

    _load_dotenv_if_present()

    agent = AIEAgent(service=AdmissionsIntelligenceService())
    task = AgentTask(
        name="llm_smoke_test",
        description="Qwen connectivity smoke test",
        agent="aie",
        payload={"prompt": args.prompt},
    )
    context = ApplicationContext(user_query=args.prompt, profile=UserProfile())
    result = agent.run(task=task, context=context)
    print(result.output.get("content", ""))


if __name__ == "__main__":
    main()
