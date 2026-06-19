from __future__ import annotations

import importlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from threading import Barrier
from typing import Any, Callable

import pytest
from _repair_prompt import write_repair_prompt


@dataclass(frozen=True)
class EngineContract:
    engine_cls: type[Any]
    store_cls: type[Any]


def fail_with_prompt(
    *,
    failed_behavior: str,
    relevant_spec_section: str,
    expected_behavior: str,
    actual_behavior: str,
    repair_instruction: str,
) -> None:
    write_repair_prompt(
        failed_behavior=failed_behavior,
        relevant_spec_section=relevant_spec_section,
        expected_behavior=expected_behavior,
        actual_behavior=actual_behavior,
        repair_instruction=repair_instruction,
    )
    pytest.fail(failed_behavior)


def load_contract() -> EngineContract:
    try:
        engine_module = importlib.import_module("src.engine")
        memory_module = importlib.import_module("src.store.memory")
        engine_cls = getattr(engine_module, "BudgetReservationEngine")
        store_cls = getattr(memory_module, "MemoryStore")
    except Exception as exc:
        fail_with_prompt(
            failed_behavior="The Budget Reservation Engine public import contract is missing.",
            relevant_spec_section=(
                "Spec 001 Memory Store Ownership: a `BudgetReservationEngine` "
                "instance owns or receives one memory store instance."
            ),
            expected_behavior=(
                "`src.engine.BudgetReservationEngine` and "
                "`src.store.memory.MemoryStore` are importable."
            ),
            actual_behavior=f"Import or lookup failed with {type(exc).__name__}: {exc}",
            repair_instruction=(
                "Provide the minimal public engine and memory store modules required by "
                "Spec 001 without changing these tests."
            ),
        )
    return EngineContract(engine_cls=engine_cls, store_cls=store_cls)


def new_engine() -> Any:
    contract = load_contract()
    return contract.engine_cls(contract.store_cls())


def assert_success(
    result: Any,
    *,
    behavior: str,
    spec: str,
    expected: str,
    repair_instruction: str,
) -> None:
    if getattr(result, "success", None) is not True:
        fail_with_prompt(
            failed_behavior=behavior,
            relevant_spec_section=spec,
            expected_behavior=expected,
            actual_behavior=f"Operation returned {result!r}.",
            repair_instruction=repair_instruction,
        )


def successful_count(results: list[Any]) -> int:
    return sum(1 for result in results if getattr(result, "success", None) is True)


def run_concurrently(call_count: int, worker: Callable[[int], Any]) -> list[Any]:
    barrier = Barrier(call_count)

    def run_one(index: int) -> Any:
        barrier.wait(timeout=5)
        return worker(index)

    with ThreadPoolExecutor(max_workers=call_count) as executor:
        return list(executor.map(run_one, range(call_count)))


def test_concurrent_reservations_with_different_ids_cannot_overspend_account() -> None:
    engine = new_engine()
    assert_success(
        engine.create_account("acct_1", Decimal("100")),
        behavior="A valid account must exist before concurrent reservation attempts.",
        spec="Spec 001 Storage: accounts are keyed by account_id.",
        expected="`create_account('acct_1', Decimal('100'))` returns success=True.",
        repair_instruction="Accept positive Decimal account balances and return a successful result object.",
    )

    results = run_concurrently(
        4,
        lambda index: engine.reserve("acct_1", f"res_{index}", Decimal("80")),
    )
    success_count = successful_count(results)
    available_balance = engine.available_balance("acct_1")
    spent_balance = engine.spent_balance("acct_1")
    reserved_or_committed_total = Decimal("80") * success_count

    if success_count > 1:
        fail_with_prompt(
            failed_behavior="Concurrent reservations must not overspend account balance.",
            relevant_spec_section=(
                "Spec 001 Concurrency Invariant: if an account has balance 100, "
                "and two threads try to reserve 80 at the same time using different "
                "reservation IDs, at most one reservation may succeed."
            ),
            expected_behavior="At most one concurrent Decimal('80') reservation returns success=True.",
            actual_behavior=f"{success_count} calls returned success from results {results!r}.",
            repair_instruction=(
                "Protect the full reserve read-modify-write operation with the MemoryStore "
                "lock so competing reservation attempts cannot all observe the same balance."
            ),
        )

    if available_balance not in {Decimal("20"), Decimal("100")}:
        fail_with_prompt(
            failed_behavior="Concurrent reservation attempts must leave a valid final available balance.",
            relevant_spec_section=(
                "Spec 001 Concurrency Invariant: final available balance must reflect "
                "successful reservations and must never go negative."
            ),
            expected_behavior=(
                "Final available balance is Decimal('20') if one reservation "
                "succeeded or Decimal('100') if all failed."
            ),
            actual_behavior=(
                f"Final available balance was {available_balance!r}; results were {results!r}."
            ),
            repair_instruction="Calculate available balance from atomically updated reservation state.",
        )

    if available_balance < Decimal("0"):
        fail_with_prompt(
            failed_behavior="Concurrent reservations must never make available balance negative.",
            relevant_spec_section="Spec 001 Concurrency Invariant: concurrent reservations must never overspend.",
            expected_behavior="Final available balance is never less than Decimal('0').",
            actual_behavior=f"Final available balance was {available_balance!r}.",
            repair_instruction="Reject reservations that would exceed available balance while holding the store lock.",
        )

    if reserved_or_committed_total > Decimal("100"):
        fail_with_prompt(
            failed_behavior="Total successful reserved plus committed spend must never exceed account balance.",
            relevant_spec_section=(
                "Spec 001 Concurrency Invariant: total active and committed spend "
                "must not exceed the account balance."
            ),
            expected_behavior="Successful Decimal('80') reservations total no more than Decimal('100').",
            actual_behavior=(
                f"Successful reservation total was {reserved_or_committed_total!r}; "
                f"spent balance was {spent_balance!r}; results were {results!r}."
            ),
            repair_instruction="Make reserve atomic and reject concurrent reservations once funds are unavailable.",
        )

    expected_available = Decimal("100") - reserved_or_committed_total
    if available_balance != expected_available:
        fail_with_prompt(
            failed_behavior="Available balance must match successful concurrent reservation outcomes.",
            relevant_spec_section=(
                "Spec 001 Concurrency Controls: balance read operations must use the "
                "same lock when reading account and reservation state."
            ),
            expected_behavior=(
                f"Available balance equals {expected_available!r} after "
                f"{success_count} successful reservations."
            ),
            actual_behavior=(
                f"Available balance was {available_balance!r}; spent balance was "
                f"{spent_balance!r}; results were {results!r}."
            ),
            repair_instruction="Read and calculate balances from the same locked store state used by reserve.",
        )


def test_repeated_concurrent_reservation_races_preserve_balance_invariant() -> None:
    for attempt in range(20):
        engine = new_engine()
        account_id = f"acct_{attempt}"
        assert_success(
            engine.create_account(account_id, Decimal("100")),
            behavior="A valid account must exist before repeated concurrent reservation attempts.",
            spec="Spec 001 Storage: accounts are keyed by account_id.",
            expected=f"`create_account({account_id!r}, Decimal('100'))` returns success=True.",
            repair_instruction="Accept positive Decimal account balances and return a successful result object.",
        )

        results = run_concurrently(
            3,
            lambda index: engine.reserve(account_id, f"res_{attempt}_{index}", Decimal("80")),
        )
        success_count = successful_count(results)
        available_balance = engine.available_balance(account_id)
        reserved_or_committed_total = Decimal("80") * success_count

        if success_count > 1 or reserved_or_committed_total > Decimal("100"):
            fail_with_prompt(
                failed_behavior="Repeated concurrent reservation races must not overspend account balance.",
                relevant_spec_section=(
                    "Spec 001 Concurrency Controls: `reserve` must be atomic with "
                    "respect to other operations on the same store."
                ),
                expected_behavior="Each race allows at most one Decimal('80') reservation against Decimal('100').",
                actual_behavior=(
                    f"Attempt {attempt} had {success_count} successes, available "
                    f"balance {available_balance!r}, and results {results!r}."
                ),
                repair_instruction=(
                    "Hold the MemoryStore lock across account lookup, duplicate reservation "
                    "check, available-balance calculation, sufficient-funds check, and reservation creation."
                ),
            )

        if available_balance not in {Decimal("20"), Decimal("100")}:
            fail_with_prompt(
                failed_behavior="Repeated concurrent reservation races must leave a valid final balance.",
                relevant_spec_section="Spec 001 Concurrency Invariant: concurrent reservations must never overspend.",
                expected_behavior=(
                    "Final available balance is Decimal('20') if one reservation "
                    "succeeded or Decimal('100') if all failed."
                ),
                actual_behavior=(
                    f"Attempt {attempt} had available balance {available_balance!r} "
                    f"after results {results!r}."
                ),
                repair_instruction=(
                    "Keep reserve and available-balance calculations synchronized "
                    "through the store lock."
                ),
            )
