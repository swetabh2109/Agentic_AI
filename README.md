# Agentic AI

A Python 3.10.4 starter for an agent that plans a step, calls a tool, and reads the result. The planner is a small rule set so the project runs with no API key. Swap `Agent.plan` for a model call when you are ready.

## Setup

The virtual environment uses the Python 3.10.4 install at `C:\Pyspark_installed\Python310\python.exe`.

```powershell
.\.venv\Scripts\Activate.ps1
python -m agentic_ai
python -m agentic_ai "echo hello"
```

## Layout

- `src/agentic_ai/agent.py` — the loop and the planner
- `src/agentic_ai/tools.py` — tools the agent can call (`calculate`, `echo`)
- `src/agentic_ai/__main__.py` — command-line entry point

Add a tool by writing a function that takes a string and returns a string, then put it in `DEFAULT_TOOLS`.
