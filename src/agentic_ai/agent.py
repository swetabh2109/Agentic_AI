"""A small rule-based agent you can later swap for an LLM planner."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentic_ai.tools import DEFAULT_TOOLS, Tool


@dataclass
class Step:
    thought: str
    tool: str
    argument: str
    observation: str


@dataclass
class Agent:
    tools: dict[str, Tool] = field(default_factory=lambda: dict(DEFAULT_TOOLS))
    max_steps: int = 4

    def run(self, task: str) -> list[Step]:
        """Run until the task is handled or the step limit is reached."""
        steps: list[Step] = []
        pending = task.strip()
        for _ in range(self.max_steps):
            tool_name, argument, thought = self.plan(pending)
            if tool_name == "finish":
                steps.append(Step(thought, "finish", argument, argument))
                break
            tool = self.tools.get(tool_name)
            if tool is None:
                observation = f"unknown tool: {tool_name}"
            else:
                observation = tool(argument)
            steps.append(Step(thought, tool_name, argument, observation))
            if observation.startswith("error:"):
                break
            pending = observation
        return steps

    def plan(self, task: str) -> tuple[str, str, str]:
        """Choose the next tool. Replace this method with an LLM call later."""
        text = task.strip()
        if text.lower().startswith("echo "):
            return "echo", text[5:].strip(), "The user asked to echo text."
        if any(ch in text for ch in "+-*/") and any(ch.isdigit() for ch in text):
            return "calculate", text, "This looks like arithmetic."
        return "finish", text, "No tool matches; return the task as the answer."
