from __future__ import annotations

import importlib
import inspect
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from threading import Barrier
from types import ModuleType
from typing import Any
from _repair_prompt import write_repair_prompt

import pytest

@dataclass(frozen=True)
class EngineContract:
    engine_cls: type[Any]
    store_cls: type[Any]
    engine_module: ModuleType
    memory_module: ModuleType



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
            failed_behavior="The Spec 001 memory engine import contract is missing.",
            relevant_spec_section=(
                "Spec 001 Memory Store Ownership: a `BudgetReservationEngine` "
                "instance owns or receives one memory store instance."
            ),
            expected_behavior=(
                "`src.engine.BudgetReservationEngine` and "
                "`src.store.memory.MemoryStore` are importable for the tests."
            ),
            actual_behavior=f"Import or lookup failed with {type(exc).__name__}: {exc}",
            repair_instruction=(
                "Create the minimal implementation modules required by the public "
                "contract without changing these tests."
            ),
        )
    return EngineContract(
        engine_cls=engine_cls,
        store_cls=store_cls,
        engine_module=engine_module,
        memory_module=memory_module,
    )


def new_engine(contract: EngineContract, store: Any | None = None) -> Any:
    if store is None:
        store = contract.store_cls()
    return contract.engine_cls(store)


def assert_success(result: Any, *, behavior: str, spec: str, expected: str) -> None:
    if getattr(result, "success", None) is not True:
        fail_with_prompt(
            failed_behavior=behavior,
            relevant_spec_section=spec,
            expected_behavior=expected,
            actual_behavior=f"Operation returned {result!r}.",
            repair_instruction="Return a result object with `success=True` for this valid operation.",
        )


def assert_decimal_equal(
    actual: Any,
    expected: Decimal,
    *,
    behavior: str,
    spec: str,
    repair_instruction: str,
) -> None:
    if actual != expected:
        fail_with_prompt(
            failed_behavior=behavior,
            relevant_spec_section=spec,
            expected_behavior=f"Expected Decimal balance {expected!r}.",
            actual_behavior=f"Observed balance {actual!r}.",
            repair_instruction=repair_instruction,
        )


def successful_count(results: list[Any]) -> int:
    return sum(1 for result in results if getattr(result, "success", None) is True)


def run_concurrently(call_count: int, worker: Any) -> list[Any]:
    barrier = Barrier(call_count)

    def run_one(index: int) -> Any:
        barrier.wait(timeout=5)
        return worker(index)

    with ThreadPoolExecutor(max_workers=call_count) as executor:
        return list(executor.map(run_one, range(call_count)))


def test_engines_with_separate_memory_stores_do_not_share_state() -> None:
    contract = load_contract()
    engine_a = new_engine(contract, contract.store_cls())
    engine_b = new_engine(contract, contract.store_cls())

    assert_success(
        engine_a.create_account("acct_shared_name", Decimal("100")),
        behavior="A valid account must be creatable in one MemoryStore instance.",
        spec="Spec 001 Storage: accounts are stored in process memory inside the memory store.",
        expected="`create_account` returns success for a new account with Decimal balance.",
    )
    assert_success(
        engine_b.create_account("acct_shared_name", Decimal("100")),
        behavior="Separate MemoryStore instances must not share account identity.",
        spec="Spec 001 Memory Store Ownership: engines with different MemoryStore instances must not share state.",
        expected="Creating the same account ID in a different MemoryStore succeeds independently.",
    )
    assert_success(
        engine_a.reserve("acct_shared_name", "res_a", Decimal("30")),
        behavior="A reservation in one MemoryStore must not affect another MemoryStore.",
        spec="Spec 001 Memory Store Ownership: engines with different MemoryStore instances must not share state.",
        expected="Reserving Decimal('30') in engine A only changes engine A's store.",
    )

    assert_decimal_equal(
        engine_a.available_balance("acct_shared_name"),
        Decimal("70"),
        behavior="Engine A should observe its own reservation.",
        spec="Spec 001 Storage: reservations belong to exactly one account in one store.",
        repair_instruction="Keep reservations scoped to the MemoryStore instance used by that engine.",
    )
    assert_decimal_equal(
        engine_b.available_balance("acct_shared_name"),
        Decimal("100"),
        behavior="Two engines with separate MemoryStore instances must not share state.",
        spec="Spec 001 Memory Store Ownership: engines with different MemoryStore instances must not share state.",
        repair_instruction="Store account and reservation state on the MemoryStore instance, not in shared globals.",
    )


def test_engines_with_same_memory_store_share_state() -> None:
    contract = load_contract()
    store = contract.store_cls()
    engine_a = new_engine(contract, store)
    engine_b = new_engine(contract, store)

    assert_success(
        engine_a.create_account("acct_1", Decimal("100")),
        behavior="A valid account must be creatable in a shared MemoryStore.",
        spec="Spec 001 Memory Store Ownership: engines constructed with the same MemoryStore observe the same state.",
        expected="`create_account` succeeds through engine A.",
    )
    assert_success(
        engine_b.reserve("acct_1", "res_1", Decimal("25")),
        behavior="Two engines with the same MemoryStore instance must share account state.",
        spec="Spec 001 Memory Store Ownership: engines constructed with the same MemoryStore observe the same state.",
        expected="Engine B can reserve against the account created by engine A.",
    )

    assert_decimal_equal(
        engine_a.available_balance("acct_1"),
        Decimal("75"),
        behavior="Two engines with the same MemoryStore instance must share reservation state.",
        spec="Spec 001 Memory Store Ownership: engines constructed with the same MemoryStore observe the same state.",
        repair_instruction="Make BudgetReservationEngine use the provided MemoryStore object for all account and reservation state.",
    )


def test_reserve_is_atomic_for_concurrent_same_reservation_id() -> None:
    contract = load_contract()
    engine = new_engine(contract)
    assert_success(
        engine.create_account("acct_1", Decimal("100")),
        behavior="A valid account must exist before concurrent reservations.",
        spec="Spec 001 Storage: accounts are keyed by account_id.",
        expected="`create_account` succeeds for Decimal('100').",
    )

    results = run_concurrently(
        12,
        lambda _index: engine.reserve("acct_1", "same_reservation", Decimal("30")),
    )

    if successful_count(results) != 12:
        fail_with_prompt(
            failed_behavior="Concurrent same-ID reservations should be idempotent successes.",
            relevant_spec_section=(
                "AGENTS.md Domain Rules: creating the same reservation twice with "
                "the same amount is idempotent. Spec 001 requires `reserve` to be atomic."
            ),
            expected_behavior="All same-ID, same-amount concurrent reserve calls return success.",
            actual_behavior=f"Observed results: {results!r}.",
            repair_instruction=(
                "Protect the full reserve read-modify-write operation with the store lock "
                "and preserve same-ID, same-amount idempotency."
            ),
        )

    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("70"),
        behavior="Concurrent same-ID reservations must reduce available balance only once.",
        spec=(
            "Spec 001 Concurrency Controls: the lock must cover the full logical "
            "`reserve` operation."
        ),
        repair_instruction=(
            "Make `reserve` atomic across existence checks, available-balance calculation, "
            "and reservation creation so duplicate concurrent calls cannot double-count spend."
        ),
    )


def test_concurrent_reservations_cannot_overspend_account_balance() -> None:
    contract = load_contract()
    engine = new_engine(contract)
    assert_success(
        engine.create_account("acct_1", Decimal("100")),
        behavior="A valid account must exist before concurrent reservations.",
        spec="Spec 001 Storage: accounts are keyed by account_id.",
        expected="`create_account` succeeds for Decimal('100').",
    )

    results = run_concurrently(
        2,
        lambda index: engine.reserve("acct_1", f"res_{index}", Decimal("80")),
    )

    if successful_count(results) != 1:
        fail_with_prompt(
            failed_behavior="Concurrent reservations must not overspend account balance.",
            relevant_spec_section=(
                "Spec 001 Concurrency Invariant: if an account has balance 100 and "
                "two threads reserve 80 with different IDs, at most one may succeed."
            ),
            expected_behavior="Exactly one of two concurrent Decimal('80') reservations succeeds.",
            actual_behavior=f"Observed results: {results!r}.",
            repair_instruction=(
                "Use the MemoryStore lock around the full reserve operation so concurrent "
                "threads cannot both observe the same available balance."
            ),
        )

    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("20"),
        behavior="Available balance must reflect only successful concurrent reservations.",
        spec="Spec 001 Concurrency Invariant: total active and committed spend must not exceed balance.",
        repair_instruction="Update available-balance calculations from locked account and reservation state.",
    )


def test_balance_reads_are_consistent_after_concurrent_reservation_attempts() -> None:
    contract = load_contract()
    engine = new_engine(contract)
    assert_success(
        engine.create_account("acct_1", Decimal("90")),
        behavior="A valid account must exist before concurrent reservations.",
        spec="Spec 001 Storage: accounts are keyed by account_id.",
        expected="`create_account` succeeds for Decimal('90').",
    )

    results = run_concurrently(
        10,
        lambda index: engine.reserve("acct_1", f"res_{index}", Decimal("15")),
    )

    expected_balance = Decimal("90") - (Decimal("15") * successful_count(results))
    if expected_balance < Decimal("0"):
        fail_with_prompt(
            failed_behavior="Concurrent reservations reported more successes than the account can fund.",
            relevant_spec_section="Spec 001 Concurrency Invariant: concurrent reservations must never overspend.",
            expected_behavior="At most six Decimal('15') reservations can succeed against Decimal('90').",
            actual_behavior=f"{successful_count(results)} calls returned success: {results!r}.",
            repair_instruction="Make reserve atomic and reject reservations that would exceed available balance.",
        )

    for _ in range(5):
        actual_balance = engine.available_balance("acct_1")
        assert_decimal_equal(
            actual_balance,
            expected_balance,
            behavior="Balance reads must be consistent after concurrent reservation attempts.",
            spec="Spec 001 Concurrency Controls: balance read operations must use the same lock.",
            repair_instruction=(
                "Read account and reservation state under the MemoryStore lock and calculate "
                "available balance from successful active reservations."
            ),
        )


def test_implementation_does_not_rely_on_module_level_global_dictionaries() -> None:
    contract = load_contract()

    global_dicts: list[str] = []
    for module in (contract.engine_module, contract.memory_module):
        for name, value in vars(module).items():
            if name.startswith("__"):
                continue
            if inspect.ismodule(value) or inspect.isclass(value) or inspect.isfunction(value):
                continue
            if isinstance(value, dict):
                global_dicts.append(f"{module.__name__}.{name}")

    if global_dicts:
        fail_with_prompt(
            failed_behavior="The memory implementation must not rely on module-level global dictionaries.",
            relevant_spec_section=(
                "Spec 001 Storage: the implementation must use a dedicated in-memory "
                "store object and must not use module-level global dictionaries."
            ),
            expected_behavior="Account and reservation dictionaries live on each MemoryStore instance.",
            actual_behavior=f"Found module-level dictionaries: {global_dicts!r}.",
            repair_instruction=(
                "Move mutable account and reservation state into MemoryStore instance attributes "
                "and have BudgetReservationEngine use the supplied store."
            ),
        )

    store_a = contract.store_cls()
    store_b = contract.store_cls()
    engine_a = new_engine(contract, store_a)
    engine_b = new_engine(contract, store_b)
    assert_success(
        engine_a.create_account("acct_global_check", Decimal("50")),
        behavior="A valid account must be creatable for global-state verification.",
        spec="Spec 001 Storage: accounts are stored in process memory inside the memory store.",
        expected="`create_account` succeeds in store A.",
    )
    assert_success(
        engine_b.create_account("acct_global_check", Decimal("50")),
        behavior="Separate MemoryStore instances must not collide through global dictionaries.",
        spec="Spec 001 Memory Store Ownership: engines with different MemoryStore instances must not share state.",
        expected="`create_account` succeeds independently in store B.",
    )
    assert_success(
        engine_a.reserve("acct_global_check", "res_global_check", Decimal("10")),
        behavior="A reservation in store A must not mutate store B through global dictionaries.",
        spec="Spec 001 Storage: account and reservation collections belong to the MemoryStore.",
        expected="Reserving in store A succeeds and only changes store A.",
    )

    assert_decimal_equal(
        engine_b.available_balance("acct_global_check"),
        Decimal("50"),
        behavior="The implementation must not rely on module-level global dictionaries.",
        spec="Spec 001 Storage: the engine must not use module-level global dictionaries.",
        repair_instruction="Remove global account/reservation dictionaries and keep mutable state on MemoryStore instances.",
    )
