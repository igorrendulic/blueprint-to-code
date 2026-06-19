# Spec 001: Memory Core Reservations

## Scope

Implement the Budget Reservation Engine using an in-memory store only.

The goal is to validate the spec → plan → agent-facing tests → implementation loop.

## Storage

All accounts and reservations are stored in process memory.

Data is lost when the process exits.

This is acceptable for Spec 001.

The implementation must use a dedicated in-memory store object. The engine must not use module-level global dictionaries.

The memory store should keep separate collections for accounts and reservations.

Conceptually, the store should behave like this:

```python
accounts: dict[str, Account]
reservations: dict[str, Reservation]
```

Where:

- `accounts` is keyed by `account_id`
- `reservations` is keyed by `reservation_id`
- each `reservation_id` must be globally unique within the store
- a reservation belongs to exactly one account

The implementation may use different internal names, but it must preserve this behavior.

## Memory Store Ownership

A `BudgetReservationEngine` instance owns or receives one memory store instance.

Two engine instances should not share state unless they are explicitly constructed with the same memory store object.

Example:

```python
store = MemoryStore()
engine_a = BudgetReservationEngine(store)
engine_b = BudgetReservationEngine(store)
```

In this case, `engine_a` and `engine_b` observe the same accounts and reservations.

Example:

```python
engine_a = BudgetReservationEngine(MemoryStore())
engine_b = BudgetReservationEngine(MemoryStore())
```

In this case, `engine_a` and `engine_b` must not share state.

## Concurrency Controls

The memory store must protect compound read-modify-write operations with a lock.

The implementation must be safe for multiple threads using the same `MemoryStore` instance.

The lock must cover the full logical operation, not only individual dictionary reads or writes.

For example, `reserve(account_id, reservation_id, amount)` must be atomic with respect to other operations on the same store:

1. Check that the account exists.
2. Check whether the reservation already exists.
3. Calculate available balance.
4. Verify sufficient available balance.
5. Create the reservation.

No other operation using the same store may observe or modify partial state between these steps.

The same requirement applies to:

- `create_account`
- `reserve`
- `commit`
- `release`

Balance read operations must also use the same lock when reading account and reservation state.

## Concurrency Scope

Spec 001 only requires thread safety inside a single Python process.

It does not require:

- multi-process safety
- distributed locking
- database transactions
- async task safety beyond normal threaded access

These are out of scope for Spec 001.

## Concurrency Invariant

Concurrent reservations must never allow total active and committed spend to exceed the account balance.

For example, if an account has balance `100`, and two threads try to reserve `80` at the same time using different reservation IDs, at most one reservation may succeed.

