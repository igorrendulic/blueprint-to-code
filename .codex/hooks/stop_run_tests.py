from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FAILURES_DIR = ROOT / "failures"
PYTEST_OUTPUT = FAILURES_DIR / "pytest_output.txt"
LATEST_FAILURE = FAILURES_DIR / "latest_failure.md"
TEST_TARGET = ROOT / "budget-reservation-engine" / "tests"


def python_executable() -> str:
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def read_latest_failure() -> str:
    if not LATEST_FAILURE.exists():
        return "No latest failure prompt was generated. Inspect failures/pytest_output.txt."
    return LATEST_FAILURE.read_text(encoding="utf-8")


def main() -> int:
    FAILURES_DIR.mkdir(exist_ok=True)

    result = subprocess.run(
        [python_executable(), "-m", "pytest", str(TEST_TARGET)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    PYTEST_OUTPUT.write_text(result.stdout, encoding="utf-8")

    if result.returncode == 0:
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return 0

    latest_failure_text = read_latest_failure()
    reason = f"""
The Budget Reservation Engine test suite failed.

Read these files:
- failures/pytest_output.txt
- failures/latest_failure.md

Then repair the implementation and try again.

Constraints:
- Do not edit tests unless they contradict the specification.
- Do not weaken the specification.
- Do not bypass or delete failure-report generation.
- Modify implementation code only unless the spec or plan is incomplete.

Latest failure summary:

{latest_failure_text[:4000]}
""".strip()

    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
