"""Deep agent: an LLM that writes its own Python scripts and runs them.

A LangChain `create_agent` with a single custom tool, `run_python`, which takes
the code the model wrote, saves it to a script file under `scripts/`, executes
it with the Python interpreter (subprocess) and returns the captured output.
The agent then reads that output and iterates until it has the right answer.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# --- Config ------------------------------------------------------------------
# DeepSeek key lives in mcp_sqlite_example/.env in this repo; also honour a
# key that is already exported in the shell.
_ENV_PATH = Path(__file__).parent / "mcp_sqlite_example" / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
SCRIPT_TIMEOUT = 30          # seconds per script run
MAX_OUTPUT_CHARS = 4000      # truncate interpreter output for the model
SCRIPTS_DIR = Path(__file__).parent / "scripts"


# --- The interpreter tool ----------------------------------------------------
@tool
def run_python(code: str) -> str:
    """Write Python code to a script file and run it with the interpreter.

    Pass the full script body as the `code` argument. The script is saved to a
    file and executed with the local Python interpreter; its stdout/stderr is
    returned. Use print() to make results visible. Use this for EVERY
    computation instead of answering from memory.
    """
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / f"agent_script_{time.time_ns()}.py"
    path.write_text(code, encoding="utf-8")

    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"Error: script timed out after {SCRIPT_TIMEOUT}s"

    out = (proc.stdout or "")
    if proc.stderr:
        out += f"\n[stderr]\n{proc.stderr}"
    if not out.strip():
        out = f"(script exited with code {proc.returncode}, no output)"
    if len(out) > MAX_OUTPUT_CHARS:
        out = out[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
    return out


SYSTEM_PROMPT = """You are an expert Python programmer agent. You have one tool,
`run_python`, which saves the Python code you give it to a script file and runs
it with the Python interpreter, returning the printed output.

Rules:
- NEVER do arithmetic or logic in your head. Write a short Python script and run
  it with `run_python` for every computation.
- Always include a `print(...)` in the script so the answer is visible.
- Read the interpreter output carefully. If the script errors, fix the bug and
  run it again.
- Only give your final answer once the script has run successfully and the
  number/result is taken directly from the observed output.
"""


def build_agent():
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Export it or add it to "
            "mcp_sqlite_example/.env"
        )
    model = ChatDeepSeek(model=MODEL)
    return create_agent(model=model, tools=[run_python], system_prompt=SYSTEM_PROMPT)


# --- Runner / transcript -----------------------------------------------------
def _print_code_block(code: str, indent: str = "    "):
    for line in code.splitlines():
        print(f"{indent}{line}")


def run(agent, question: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    final_answer = ""
    for msg in result["messages"]:
        if isinstance(msg, HumanMessage):
            print("=" * 70)
            print(f"USER: {msg.content}")
        elif isinstance(msg, AIMessage):
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    print("-" * 70)
                    print(f"ACTION: {tc['name']}(code=...)")
                    print("  script:")
                    _print_code_block(tc["args"].get("code", ""))
            if msg.content:
                print(f"ANSWER: {msg.content}")
                final_answer = msg.content
        elif isinstance(msg, ToolMessage):
            print("  -> interpreter output:")
            _print_code_block(msg.content)
    return final_answer


if __name__ == "__main__":
    agent = build_agent()

    tasks = [
        ("Fibonacci",
         "Write and run a script that prints the first 20 Fibonacci numbers."),
        ("Sum of squares",
         "Write and run a script that prints the sum of the squares of the "
         "integers from 1 to 10."),
        ("Self-correct",
         "Write and run a script that prints all prime numbers below 100."),
    ]

    for title, question in tasks:
        print("\n" + "#" * 70)
        print(f"# TASK — {title}")
        print("#" * 70)
        final = run(agent, question)
        print("-" * 70)
        print(f"FINAL ANSWER: {final}")
