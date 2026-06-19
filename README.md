# Reproducible Software Generation from Specifications, Plans, and Tests

## Overview

This repository is an experiment in specification-driven software development using AI coding agents.

The goal is to determine whether a software system can be reliably generated from:

1. A written specification
2. An implementation plan
3. A suite of behavior-focused tests

without requiring a human to manually write the implementation.

The project intentionally starts with a small domain — a Budget Reservation Engine — to make correctness easy to reason about while still requiring non-trivial business rules, state management, idempotency, and concurrency controls.

## Start Implementation

Paste this into Codex:

```text
Implement the project.

Read:
- AGENTS.md
- specs/

Continue until the full test suite passes.

If tests fail, read:
- failures/latest_failure.md
- failures/pytest_output.txt

Then fix the implementation and run the tests again.

Do not edit tests unless they contradict the specification.
Do not weaken the specification.
Do not bypass the test suite.
```

---

## Codex Test Hook

This repository is designed to use a Codex `Stop` hook as a test gate.

The hook should run the full test suite whenever Codex tries to finish a turn. If tests fail, the hook blocks completion and gives Codex a continuation prompt that points it to the failure files.

The hook should not recursively launch Codex. It should only:

1. Run tests
2. Capture raw test output
3. Let the tests write `failures/latest_failure.md`
4. Block completion if tests fail
5. Allow completion if tests pass

Recommended project-local Codex config:

```toml
# .codex/config.toml

[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = '/usr/bin/python3 "$(git rev-parse --show-toplevel)/.codex/hooks/stop_run_tests.py"'
timeout = 120
statusMessage = "Running full test suite"
```

Recommended hook script:

```python
# .codex/hooks/stop_run_tests.py

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FAILURES_DIR = ROOT / "failures"
PYTEST_OUTPUT = FAILURES_DIR / "pytest_output.txt"
LATEST_FAILURE = FAILURES_DIR / "latest_failure.md"


def main() -> int:
    FAILURES_DIR.mkdir(exist_ok=True)

    result = subprocess.run(
        ["uv", "run", "pytest"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    PYTEST_OUTPUT.write_text(result.stdout)

    if result.returncode == 0:
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return 0

    latest_failure_text = ""
    if LATEST_FAILURE.exists():
        latest_failure_text = LATEST_FAILURE.read_text()

    reason = f"""
The full test suite failed.

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
```

Codex hooks are loaded from project-local config files such as `.codex/config.toml` or `.codex/hooks.json`. Project-local hooks must be reviewed and trusted before Codex runs them.

---

## Premise

Modern coding agents are capable of generating large amounts of code, but code generation alone is not the interesting problem.

The interesting question is:

> Can we create a repeatable process where the same specification consistently produces a correct implementation?

If the answer is yes, software development shifts from writing code to defining behavior.

Instead of:

```text
Human
  ↓
Code
```

The workflow becomes:

```text
Human
  ↓
Specification
  ↓
Plan
  ↓
Tests
  ↓
Agent
  ↓
Implementation
```

The implementation becomes a derived artifact rather than the primary source of truth.

---

## Hypothesis

Given:

- a sufficiently precise specification
- a sufficiently detailed implementation plan
- a test suite that accurately describes expected behavior
- a hook-enforced repair loop

an AI coding agent should be able to repeatedly generate a correct implementation.

More importantly:

> The implementation should be reproducible.

If the implementation is deleted and regenerated from the same inputs, the resulting behavior should remain correct.

---

## Why This Experiment Exists

Most AI coding workflows today operate like this:

```text
Prompt
  ↓
Code
  ↓
Fix bugs
  ↓
More code
```

This often leads to:

- implementation drift
- inconsistent architecture
- accidental feature additions
- weak guarantees about correctness

This repository explores a different approach:

```text
Specification
  ↓
Plan
  ↓
Behavior Tests
  ↓
Generated Code
  ↓
Hook-Enforced Test Run
  ↓
Automated Repair Loop
```

The objective is not merely generating code.

**The objective is generating correct behavior.**

---

## Core Principles

### Specification Is the Source of Truth

Specifications define behavior.

Implementation details are secondary.

If the implementation and specification disagree, the specification wins.

### Plans Describe Strategy

Plans explain how a specification should be implemented.

Plans may reference architecture, domain models, storage choices, and tradeoffs.

Plans do not contain implementation code.

### Tests Describe Behavior

Tests validate externally observable behavior.

Tests should avoid unnecessary coupling to implementation details.

Whenever possible, tests should verify:

- inputs
- outputs
- state transitions
- invariants

rather than specific internal implementation choices.

### Hooks Enforce Completion

The Codex hook is not the orchestrator.

The hook does not launch Codex again.

The hook only enforces the project rule:

> A task is not complete until the full test suite passes.

If tests fail, Codex receives a continuation prompt with the relevant failure files.

### Implementations Are Disposable

Implementations may be deleted and regenerated.

The long-term value of the project lives in:

- specifications
- plans
- tests
- failure prompts

not in any individual implementation.

---

## Agent Repair Loop

The project uses an automated repair cycle:

```text
Specification
  ↓
Plan
  ↓
Tests
  ↓
Implementation
  ↓
Stop Hook
  ↓
Full Test Suite
  ↓
Test Failure
  ↓
Repair Prompt
  ↓
Implementation Update
  ↓
Tests
```

When tests fail, they may generate machine-readable repair instructions in:

```text
failures/latest_failure.md
```

The hook captures raw test output in:

```text
failures/pytest_output.txt
```

The coding agent can then use:

- the specification
- the implementation plan
- the failing test output
- generated repair prompts

to update the implementation until the full test suite passes.

---

## Success Criteria

This experiment is successful if:

1. A new implementation can be generated from the specification and plan.
2. The generated implementation passes the full test suite.
3. The implementation can be deleted and regenerated repeatedly.
4. The resulting behavior remains correct.
5. Human involvement is limited to defining behavior rather than writing code.

---

## Current Domain

The initial domain is a **Budget Reservation Engine**.

The engine supports:

- account creation
- budget reservations
- reservation commits
- reservation releases
- balance calculations
- concurrency guarantees

The domain is intentionally small but contains enough complexity to evaluate whether specification-driven generation works in practice.

---

## Long-Term Goal

The Budget Reservation Engine is not the destination.

It is the test case.

The broader goal is to determine whether a repository can be structured such that:

```text
specification + plan + tests + failure prompts
```

are sufficient for a coding agent to reliably recreate the implementation from scratch.

If that works consistently, software projects become reproducible systems rather than collections of handwritten source files.
