"""
Joinloop · Session 3 · Live Demo 1
"An agent that remembers across turns" — LangGraph + MemorySaver

WHAT THIS SHOWS (say this out loud while walking the code):
  1. Memory is NOT something the LLM has natively. Every call to an LLM is stateless.
  2. LangGraph gives an agent memory by checkpointing conversation state under a
     `thread_id`. Same thread_id -> same history is replayed in. Different thread_id
     -> the agent has never "met" you.
  3. This is the simplest form of memory from slide 6: in-context / short-term,
     backed by a checkpointer instead of you manually re-sending history.

SETUP (2 min):
  # Requires Python 3.10-3.13 (crewai/langgraph do not yet support 3.14).
  # If your system `python3` is 3.14, create a venv with an older Python first:
  #   python3.12 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  export GROQ_API_KEY=gsk_...
  python demo1_memory_agent.py            # scripted, safe run for the room
  python demo1_memory_agent.py --live     # you type the turns live

  # Model note: this uses openai/gpt-oss-20b on Groq. llama-3.3-70b-versatile
  # (and other llama-* chat models) are no longer served on Groq's free tier —
  # run `curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"`
  # to see exactly which models your key can use before the session.

WALKTHROUGH ORDER FOR THE SESSION:
  - build_agent(): point at the `checkpointer = MemorySaver()` line first.
    That single object is the entire difference between "chatbot" and "stateful agent."
  - ask(): point at `config = {"configurable": {"thread_id": thread_id}}`.
    This is the only thing that ties a message to a memory.
  - Then run it. Turn 1 tells the agent your name. Turn 2 (same thread) recalls it.
    Turn 3 (new thread) proves the memory is scoped, not global.
"""

import os
import sys

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq


def build_agent():
    llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)
    checkpointer = MemorySaver()  # <-- this line is the whole demo
    return create_react_agent(llm, tools=[], checkpointer=checkpointer)


def ask(agent, thread_id: str, message: str) -> str:
    config = {"configurable": {"thread_id": thread_id}}  # <-- and this line
    result = agent.invoke({"messages": [("user", message)]}, config)
    return result["messages"][-1].content


# A safe, scripted run in case live typing eats time you don't have.
SCRIPT = [
    ("thread-A", "Hi, I'm Pallav. I'm running a workshop on multi-agent systems today."),
    ("thread-A", "Quick check — what's my name, and what am I doing today?"),
    ("thread-B", "What's my name?"),  # fresh thread_id -> agent has no idea
]


def run_scripted(agent):
    for thread_id, msg in SCRIPT:
        print(f"\n[{thread_id}] USER : {msg}")
        print(f"[{thread_id}] AGENT: {ask(agent, thread_id, msg)}")
    print(
        "\n--> Notice thread-B has no memory of thread-A. "
        "Memory lives in the checkpointer, scoped by thread_id — not in the model."
    )


def run_live(agent):
    print("Live mode. Prefix a line with 'THREAD: ' to switch threads (default thread is A).")
    print("Try: tell it your name on thread A, ask it to recall on thread A, "
          "then switch to thread B and ask again. Ctrl+C to quit.\n")
    thread_id = "A"
    while True:
        raw = input(f"[{thread_id}] you> ").strip()
        if not raw:
            continue
        if raw[0].isalpha() and ":" in raw.split(" ")[0]:
            head, rest = raw.split(":", 1)
            if rest.strip():
                thread_id, raw = head.strip(), rest.strip()
        print(f"[{thread_id}] agent> {ask(agent, thread_id, raw)}\n")


if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        sys.exit("Set GROQ_API_KEY before running this demo.")
    agent = build_agent()
    if "--live" in sys.argv:
        run_live(agent)
    else:
        run_scripted(agent)
