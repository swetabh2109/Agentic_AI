"""Run the starter agent from the command line."""

from __future__ import annotations

import sys

from agentic_ai.agent import Agent


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    task = " ".join(args).strip() or "2 + 2 * 3"
    agent = Agent()
    print(f"task: {task}")
    for index, step in enumerate(agent.run(task), start=1):
        print(f"step {index}")
        print(f"  thought: {step.thought}")
        print(f"  tool: {step.tool}({step.argument})")
        print(f"  observation: {step.observation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
