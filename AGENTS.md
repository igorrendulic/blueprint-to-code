# PROJECT KNOWLEDGE BASE

This file provides guidance to AI agents when working with code in this repository.

## KEY NOTES

- Python deps live in a `uv`-managed virtualenv at `.venv` (repo root). If it doesn't exist yet, create it with `uv sync --frozen`, then `source .venv/bin/activate`.

## Project Overview

Budget Reservation Engine is a small Python library for reserving, committing, and releasing budget before executing work.
The project is designed as a spec-first coding experiment:

specification
  ↓
implementation plan
  ↓
agent-facing tests
  ↓
implementation
  ↓
failure report / repair prompt
  ↓
implementation patch

The goal is to test whether AI coding agents can reliably implement correct behavior from:

1. A written specification
2. An implementation plan
3. Tests that generate repair prompts when behavior fails

### Code Quality

```bash
# Install and run pre-commit hooks
pre-commit install
pre-commit run --all-files
```

NOTE: Always make sure everything is strictly typed (both in Python and Typescript).

## Architecture Overview

### Technology Stack

- **Language**: Python 3.13, FastAPI
- **AI/ML**: codex, claude

### Directory Structure

```
budget-reservation-engine/
├── src/
│   ├── store/
│   │   ├── memory.py               # Memory for storing budget reservations
│   ├──engine.py                   # Core budget reservation engine
│   ├──utils.py                    # Budget reservation util methods
│   ├── domain.py                   # only business concepts and business rules, not storage or orchestration (e.g. @dataclass ReservationStatus, @dataclass Account, ...)
└── tests/                      # Test suites
failures/latest_failure.md        # unsucsessful implementation storage with instructions for repair
```
## Testing Strategy

First, activate the virtualenv: `source .venv/bin/activate`. If `.venv` doesn't exist yet, create it first with `uv sync --frozen`.

Run tests with `pytest`

**Tests in this project are agent-facing tests.** When a behavior fails, the test should write a repair prompt to: `failures/latest_filure.md`

The failure report should include:
- failed behavior
- relevant spec section
- expected behavior
- actual behavior
- repair instruction
- constraints for the coding agent

Example failure report shape:
```md
# Repair Prompt

You are fixing the Budget Reservation Engine implementation.

## Failed behavior

Creating a reservation must reduce available balance.

## Relevant spec

Rule 2: Creating a reservation decreases available balance.

## Expected behavior

`reserve("acct_1", "res_1", Decimal("30"))` returns `success=True`
and `available_balance("acct_1") == Decimal("70")`.

## Actual behavior

`success=True`, but `available_balance("acct_1") == Decimal("100")`.

## Repair instruction

Ensure active reservations reduce available balance.

## Constraints

- Modify implementation code only.
- Do not modify tests.
- Do not weaken the specification.
- Keep the implementation minimal.
- Do not add behavior outside the spec.
```

## Agent Repair Loop

When using Codex or another coding agent, use this loop:
```
pytest tests/eval_core_reservations.py
```

If tests fail:

1. Read failures/latest_failure.md
2. Patch the implementation
3. Re-run the tests
4. Repeat until tests pass

The agent must not edit the tests unless explicitly instructed.

## Creating a Plan

When creating a plan in the `plans` directory, make sure to include at least these elements:

**Issues to Address**
What the change is meant to do.

**Important Notes**
Things you come across in your research that are important to the implementation.

**Implementation strategy**
How you are going to make the changes happen. High level approach.

**Tests**
Describe the tests that should verify the behavior.

Prefer behavior-level tests over implementation-detail tests.

Use agent-facing tests when possible.

Do not overtest. A given change usually needs only a small number of focused tests.

Before writing a plan, inspect the relevant files and read the relevant specification.

## Error Handling

Expected business failures should return explicit result objects, not raise exceptions.

Examples of expected failures:

- account does not exist
- reservation does not exist
- insufficient available balance
- reservation already committed
- reservation already released
- invalid amount

Example result shape:

```python
@dataclass(frozen=True)
class Result:
    success: bool
    error_code: str | None = None
    message: str | None = None
```
Unexpected programmer errors may raise exceptions.

Do not introduce HTTP exceptions or web-framework error types.

## Domain Rules

The implementation must follow the written specification.

Important initial rules:

1. A reservation may be created only if amount <= available_balance.
2. Creating a reservation decreases available balance.
3. Creating the same reservation twice with the same amount is idempotent.
4. Creating the same reservation twice with a different amount must fail.
5. Committing an active reservation increases spent balance.
6. Releasing an active reservation restores available balance.
7. Committing a non-existent reservation fails.
8. Releasing a non-existent reservation fails.
9. Committing an already committed reservation is idempotent.
10. Releasing an already released reservation is idempotent.
11. A committed reservation cannot be released.
12. A released reservation cannot be committed.
13. Amounts must be positive.
14. Money values must use Decimal, not float.

## Storage Guidance

### In-Memory Store

The implementation should use a simple in-memory store.

Use this for:

- core behavior
- fast tests
- initial spec-to-code experiments

## Best Practices

- Read the specification before changing code.
- Keep changes minimal.
- Prefer explicit domain behavior over clever abstractions.
- Do not add infrastructure before the spec requires it.
- Do not introduce web APIs in the core library.
- Do not silently change tests to make implementation pass.
- Do not weaken failure prompts.
- Every behavior change should be reflected in the spec, plan, or tests.

## Definition of Done

An implementation is complete only when:

1. The full test suite passes.
2. No repair prompts are generated.
3. No files in failures/ indicate unresolved issues.

Agents must never declare success before the test suite passes.

## Test Enforcement

The repository is hook-enforced.

Agents must assume that the full test suite will be executed after implementation changes.

A task is not complete until:
- all tests pass
- no repair prompts are generated
- failures/latest_failure.md does not contain unresolved failures