"""
Joinloop · Session 3 · Live Demo 2
Research -> Write -> Review — a 3-agent CrewAI pipeline with scoped handoffs

WHAT THIS SHOWS (say this out loud while walking the code):
  1. Three agents, three narrow roles (Architect->Builder->Review analogy from slide 8).
  2. Each Task's `context=[...]` is the ONLY thing another agent gets to see.
     The Writer never sees the Reviewer's instructions. The Reviewer never sees the
     Researcher's raw prompt — only its output. That's "scoped context" in practice:
     it's what stops one agent's confusion from leaking into and corrupting the next.
  3. process=Process.sequential is a pipeline topology (slide 7): output of one task
     becomes input to the next, in a straight line — no manager, no back-and-forth.

SETUP (2 min):
  # Requires Python 3.10-3.13 (crewai/langgraph do not yet support 3.14).
  # If your system `python3` is 3.14, create a venv with an older Python first:
  #   python3.12 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  export GROQ_API_KEY=gsk_...
  export CREWAI_TRACING_ENABLED=true   # optional, off by default. Answer "y" at the
                                        # end-of-run share prompt to get a viewable
                                        # app.crewai.com link -- declining/timeout (the
                                        # default) leaves nothing viewable; there's no
                                        # local trace log/UI in the OSS version.
  python demo2_research_write_review.py
  python demo2_research_write_review.py "why do multi-agent systems need topologies?"

  # Model note: this uses openai/gpt-oss-20b on Groq. llama-3.3-70b-versatile
  # (and other llama-* chat models) are no longer served on Groq's free tier —
  # run `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"`
  # to see exactly which models your key can use before the session.
  # Also note: crewai's LLM class routes non-native providers (Groq included)
  # through the `litellm` package, so it must be installed even though nothing
  # in this file imports it directly — it's in requirements.txt for that reason.

NOTE: this intentionally has no external search tool wired in (no SerperDev/Tavily
key needed) so it runs live in under a minute. In production you'd give the
Researcher a real search tool (see slide 12 in the original deck for that pattern) —
say that explicitly so the room doesn't think this is how you'd ship it.
"""

import os
import sys

from crewai import Agent, Task, Crew, Process, LLM

# crewai tags messages with an internal 'cache_breakpoint' marker (used to signal
# Anthropic-style prompt caching). Native provider adapters strip it, but the
# litellm fallback path -- which is what handles Groq -- does not, so Groq's API
# rejects the request with "property 'cache_breakpoint' is unsupported". Patch
# the fallback path to strip it before every completion call.
_orig_prepare_completion_params = LLM._prepare_completion_params


def _prepare_completion_params_no_cache_breakpoint(self, *args, **kwargs):
    params = _orig_prepare_completion_params(self, *args, **kwargs)
    for message in params.get("messages", []):
        if isinstance(message, dict):
            message.pop("cache_breakpoint", None)
    return params


LLM._prepare_completion_params = _prepare_completion_params_no_cache_breakpoint


def build_crew(topic: str) -> Crew:
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

    research_task = Task(
        description=f"Research this topic: {topic}. Produce exactly 4 bullet-point facts, one sentence each.",
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
        context=[research_task],  # <-- scoped handoff: writer sees research output only
    )

    review_task = Task(
        description=(
            "Compare the draft to the original research facts. If every claim in the "
            "draft traces back to a fact, reply APPROVED. Otherwise, list exactly one "
            "specific fix needed."
        ),
        expected_output="Either the word APPROVED, or one specific, actionable fix.",
        agent=reviewer,
        context=[research_task, write_task],  # <-- reviewer sees both, still scoped
    )

    return Crew(
        agents=[researcher, writer, reviewer],
        tasks=[research_task, write_task, review_task],
        process=Process.sequential,
        verbose=True,
    )


if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("Set GROQ_API_KEY before running this demo.")

    topic = " ".join(sys.argv[1:]) or "why do AI agents need memory?"
    print(f"\nRunning Research -> Write -> Review on: {topic!r}\n")

    crew = build_crew(topic)
    result = crew.kickoff()

    print("\n=== FINAL OUTPUT ===\n")
    print(result.raw)