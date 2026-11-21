"""
Joinloop · Session 3 · Hands-On Exercise
Give the Research -> Write -> Review crew memory across runs

Memory here is a small JSON file on disk (crew_memory.json), keyed by topic.
Run 1 saves the Researcher's facts. Run 2 (same topic) feeds them back to the
Researcher so it reuses and refines them instead of starting from scratch.

USAGE:
  python crew_memory_starter.py "why do AI agents need memory?"
  python crew_memory_starter.py "why do AI agents need memory?"   # run again, same topic
  python crew_memory_starter.py --show-memory                    # peek at what got saved
"""

import json
import os
import sys

from crewai import Agent, Task, Crew, Process, LLM

# crewai tags messages with an internal 'cache_breakpoint' marker. The litellm
# fallback path (used for Groq) doesn't strip it, so Groq rejects the request.
# Patch the fallback path to remove it before every completion call.
_orig_prepare_completion_params = LLM._prepare_completion_params


def _prepare_completion_params_no_cache_breakpoint(self, *args, **kwargs):
    params = _orig_prepare_completion_params(self, *args, **kwargs)
    for message in params.get("messages", []):
        if isinstance(message, dict):
            message.pop("cache_breakpoint", None)
    return params


LLM._prepare_completion_params = _prepare_completion_params_no_cache_breakpoint

MEMORY_FILE = "crew_memory.json"


def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return {}


def save_memory(memory: dict) -> None:
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def build_crew(topic: str, prior_facts: str | None) -> Crew:
    llm = LLM(model="groq/openai/gpt-oss-20b", temperature=0.3)

    researcher = Agent(
        role="Research Analyst",
        goal=f"Find 4 crisp, accurate facts about: {topic}",
        backstory="You dig up the sharpest, most relevant facts. You only ever output facts, never prose.",
        llm=llm,
        verbose=True,
    )

    writer = Agent(
        role="Technical Writer",
        goal="Turn raw research facts into a tight, engaging explainer",
        backstory=(
            "You take research notes and turn them into clear, punchy writing for a "
            "mixed engineer/PM audience. You do not invent new facts beyond what you're given."
        ),
        llm=llm,
        verbose=True,
    )

    reviewer = Agent(
        role="Editor",
        goal="Check the draft against the original facts for accuracy and clarity",
        backstory=(
            "You are a strict but fair editor. You only ever check what's in front of "
            "you — you never add new claims of your own."
        ),
        llm=llm,
        verbose=True,
    )

    research_description = f"Research this topic: {topic}. Produce exactly 4 bullet-point facts, one sentence each."

    # TODO 1: inject prior facts into the Researcher's task prompt.
    if prior_facts:
        research_description += (
            "\n\nYou already researched this topic before. Here are your "
            f"prior facts — reuse and refine them, don't start over:\n{prior_facts}"
        )

    research_task = Task(
        description=research_description,
        expected_output="4 bullet-point facts, nothing else.",
        agent=researcher,
    )

    write_task = Task(
        description=(
            "Using ONLY the facts above (do not add new ones), write a punchy "
            "120-word explainer suitable for a live workshop slide."
        ),
        expected_output="A single ~120-word explainer paragraph.",
        agent=writer,
        context=[research_task],
    )

    review_task = Task(
        description=(
            "Compare the draft to the original research facts. If every claim in the "
            "draft traces back to a fact, reply APPROVED. Otherwise, list exactly one "
            "specific fix needed."
        ),
        expected_output="Either the word APPROVED, or one specific, actionable fix.",
        agent=reviewer,
        context=[research_task, write_task],
    )

    return Crew(
        agents=[researcher, writer, reviewer],
        tasks=[research_task, write_task, review_task],
        process=Process.sequential,
        verbose=True,
    )


# STRETCH GOAL (not implemented): also save the Writer's approved draft, and on a
# repeat run where the Reviewer approves, skip the Writer and reuse the stored draft.


def main():
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("Set GROQ_API_KEY before running this exercise.")

    memory = load_memory()

    if "--show-memory" in sys.argv:
        # json.dumps({}) is the truthy string "{}", so check the dict itself.
        print(json.dumps(memory, indent=2) if memory else "{} (empty)")
        return

    topic = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or "why do AI agents need memory?"
    prior_facts = memory.get(topic)

    print(f"\nRunning Research -> Write -> Review on: {topic!r}")
    print("Prior facts found in memory — reusing them." if prior_facts else "No prior memory for this topic — starting fresh.")

    crew = build_crew(topic, prior_facts)
    result = crew.kickoff()

    # TODO 2: persist this run's research facts, keyed by topic.
    memory[topic] = result.tasks_output[0].raw
    save_memory(memory)

    print("\n=== FINAL OUTPUT ===\n")
    print(result.raw)


if __name__ == "__main__":
    main()