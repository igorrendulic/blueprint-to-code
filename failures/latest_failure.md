# Repair Prompt

You are fixing the Budget Reservation Engine implementation.

## Failed behavior

The Spec 001 memory engine import contract is missing.

## Relevant spec section

Spec 001 Memory Store Ownership: a `BudgetReservationEngine` instance owns or receives one memory store instance.

## Expected behavior

`src.engine.BudgetReservationEngine` and `src.store.memory.MemoryStore` are importable for the tests.

## Actual behavior

Import or lookup failed with ModuleNotFoundError: No module named 'src.engine'

## Repair instruction

Create the minimal implementation modules required by the public contract without changing these tests.

## Constraints

- Modify implementation code only.
- Do not modify tests.
- Do not weaken or reinterpret Spec 001.
- Do not add Redis, database, API, async worker, or persistence behavior.
- Keep all Spec 001 storage in process memory.
- Use Decimal for money values, not float.
- Do not rely on module-level global dictionaries for account or reservation state.
