from __future__ import annotations

import importlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

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


def assert_failure(
    result: Any,
    *,
    behavior: str,
    spec: str,
    expected: str,
    repair_instruction: str,
) -> None:
    if getattr(result, "success", None) is not False:
        fail_with_prompt(
            failed_behavior=behavior,
            relevant_spec_section=spec,
            expected_behavior=expected,
            actual_behavior=f"Operation returned {result!r}.",
            repair_instruction=repair_instruction,
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
            expected_behavior=f"Expected Decimal value {expected!r}.",
            actual_behavior=f"Observed value {actual!r}.",
            repair_instruction=repair_instruction,
        )


def create_account(engine: Any, account_id: str = "acct_1") -> None:
    assert_success(
        engine.create_account(account_id, Decimal("100")),
        behavior="Creating a valid account with Decimal balance must succeed.",
        spec="AGENTS.md Domain Rules: money values must use Decimal, not float.",
        expected="`create_account(account_id, Decimal('100'))` returns success=True.",
        repair_instruction="Accept positive Decimal account balances and return a successful result object.",
    )


def test_basic_reservation_lifecycle_commits_spend_without_restoring_available_balance() -> None:
    engine = new_engine()
    create_account(engine)

    assert_success(
        engine.reserve("acct_1", "res_1", Decimal("30")),
        behavior="Creating a reservation must reduce available balance.",
        spec=(
            "AGENTS.md Domain Rules 1, 2, and 5: a reservation may be created only "
            "if amount <= available_balance; creating a reservation decreases "
            "available balance; committing an active reservation increases spent balance."
        ),
        expected="`reserve('acct_1', 'res_1', Decimal('30'))` returns success=True.",
        repair_instruction="Create active reservations for valid positive Decimal amounts when funds are available.",
    )
    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("70"),
        behavior="Creating a reservation must reduce available balance.",
        spec="AGENTS.md Domain Rule 2: creating a reservation decreases available balance.",
        repair_instruction="Subtract active reservations when calculating available balance.",
    )
    assert_decimal_equal(
        engine.spent_balance("acct_1"),
        Decimal("0"),
        behavior="Creating a reservation must not increase spent balance before commit.",
        spec="AGENTS.md Domain Rule 5: committing an active reservation increases spent balance.",
        repair_instruction="Count only committed reservations in spent balance.",
    )

    assert_success(
        engine.commit("res_1"),
        behavior="Committing an active reservation must succeed.",
        spec="AGENTS.md Domain Rule 5: committing an active reservation increases spent balance.",
        expected="`commit('res_1')` returns success=True.",
        repair_instruction="Allow active reservations to transition to committed.",
    )
    assert_decimal_equal(
        engine.spent_balance("acct_1"),
        Decimal("30"),
        behavior="Committing an active reservation must increase spent balance.",
        spec="AGENTS.md Domain Rule 5: committing an active reservation increases spent balance.",
        repair_instruction="Include committed reservations when calculating spent balance.",
    )
    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("70"),
        behavior="Committing a reservation must not restore available balance.",
        spec=(
            "Spec 001 Concurrency Invariant: total active and committed spend must "
            "not exceed the account balance."
        ),
        repair_instruction="Continue treating committed reservations as unavailable funds.",
    )


def test_release_lifecycle_restores_available_balance_without_spending() -> None:
    engine = new_engine()
    create_account(engine)
    assert_success(
        engine.reserve("acct_1", "res_1", Decimal("30")),
        behavior="A valid reservation must be creatable before release.",
        spec="AGENTS.md Domain Rule 1: a reservation may be created only if amount <= available_balance.",
        expected="`reserve('acct_1', 'res_1', Decimal('30'))` returns success=True.",
        repair_instruction="Create valid active reservations before release.",
    )

    assert_success(
        engine.release("res_1"),
        behavior="Releasing an active reservation must succeed.",
        spec="AGENTS.md Domain Rule 6: releasing an active reservation restores available balance.",
        expected="`release('res_1')` returns success=True.",
        repair_instruction="Allow active reservations to transition to released.",
    )
    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("100"),
        behavior="Releasing an active reservation must restore available balance.",
        spec="AGENTS.md Domain Rule 6: releasing an active reservation restores available balance.",
        repair_instruction="Exclude released reservations from unavailable funds.",
    )
    assert_decimal_equal(
        engine.spent_balance("acct_1"),
        Decimal("0"),
        behavior="Releasing a reservation must not increase spent balance.",
        spec="AGENTS.md Domain Rule 6: releasing an active reservation restores available balance.",
        repair_instruction="Do not count released reservations as committed spend.",
    )


def test_overspend_prevention_keeps_available_balance_unchanged_after_failed_reserve() -> None:
    engine = new_engine()
    create_account(engine)
    assert_success(
        engine.reserve("acct_1", "res_1", Decimal("80")),
        behavior="The first affordable reservation must succeed.",
        spec="AGENTS.md Domain Rule 1: a reservation may be created only if amount <= available_balance.",
        expected="`reserve('acct_1', 'res_1', Decimal('80'))` returns success=True.",
        repair_instruction="Allow reservations that are fully covered by available balance.",
    )

    result = engine.reserve("acct_1", "res_2", Decimal("30"))
    assert_failure(
        result,
        behavior="Reservations that exceed available balance must fail.",
        spec="AGENTS.md Domain Rule 1: a reservation may be created only if amount <= available_balance.",
        expected="A second Decimal('30') reservation fails when only Decimal('20') remains available.",
        repair_instruction="Reject reservations that exceed current available balance and return success=False.",
    )
    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("20"),
        behavior="A failed reservation must not change available balance.",
        spec=(
            "AGENTS.md Domain Rule 1: a reservation may be created only if amount "
            "<= available_balance."
        ),
        repair_instruction="Do not create or mutate reservation state when funds are insufficient.",
    )


def test_reserve_same_id_same_amount_is_idempotent_without_double_reserving() -> None:
    engine = new_engine()
    create_account(engine)

    for _ in range(2):
        assert_success(
            engine.reserve("acct_1", "res_1", Decimal("30")),
            behavior="Reserving the same reservation ID with the same amount must be idempotent.",
            spec=(
                "AGENTS.md Domain Rule 3: creating the same reservation twice with "
                "the same amount is idempotent."
            ),
            expected="Both reserve calls return success=True.",
            repair_instruction="Return success for same-ID, same-amount duplicate reserve calls.",
        )

    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("70"),
        behavior="Idempotent reserve must not double-reserve funds.",
        spec=(
            "AGENTS.md Domain Rule 3: creating the same reservation twice with "
            "the same amount is idempotent."
        ),
        repair_instruction=(
            "Do not create a second active reservation or subtract funds twice for "
            "an idempotent reserve."
        ),
    )


def test_committing_same_reservation_twice_is_idempotent_without_double_counting_spend() -> None:
    engine = new_engine()
    create_account(engine)
    assert_success(
        engine.reserve("acct_1", "res_1", Decimal("30")),
        behavior="A valid reservation must be creatable before commit idempotency is tested.",
        spec="AGENTS.md Domain Rule 1: a reservation may be created only if amount <= available_balance.",
        expected="`reserve('acct_1', 'res_1', Decimal('30'))` returns success=True.",
        repair_instruction="Create valid active reservations before commit.",
    )

    for _ in range(2):
        assert_success(
            engine.commit("res_1"),
            behavior="Committing an already committed reservation must be idempotent.",
            spec="AGENTS.md Domain Rule 9: committing an already committed reservation is idempotent.",
            expected="Both commit calls return success=True.",
            repair_instruction="Return success for duplicate commits without applying spend twice.",
        )

    assert_decimal_equal(
        engine.spent_balance("acct_1"),
        Decimal("30"),
        behavior="Idempotent commit must not double-count spent balance.",
        spec="AGENTS.md Domain Rule 9: committing an already committed reservation is idempotent.",
        repair_instruction="Keep committed reservation amount counted exactly once in spent balance.",
    )
    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("70"),
        behavior="Idempotent commit must not change available balance twice.",
        spec="AGENTS.md Domain Rule 9: committing an already committed reservation is idempotent.",
        repair_instruction="Do not mutate balances again when commit is repeated for an already committed reservation.",
    )


def test_releasing_same_reservation_twice_is_idempotent_without_changing_balances_twice() -> None:
    engine = new_engine()
    create_account(engine)
    assert_success(
        engine.reserve("acct_1", "res_1", Decimal("30")),
        behavior="A valid reservation must be creatable before release idempotency is tested.",
        spec="AGENTS.md Domain Rule 1: a reservation may be created only if amount <= available_balance.",
        expected="`reserve('acct_1', 'res_1', Decimal('30'))` returns success=True.",
        repair_instruction="Create valid active reservations before release.",
    )

    for _ in range(2):
        assert_success(
            engine.release("res_1"),
            behavior="Releasing an already released reservation must be idempotent.",
            spec="AGENTS.md Domain Rule 10: releasing an already released reservation is idempotent.",
            expected="Both release calls return success=True.",
            repair_instruction="Return success for duplicate releases without restoring funds twice.",
        )

    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("100"),
        behavior="Idempotent release must not restore available balance twice.",
        spec="AGENTS.md Domain Rule 10: releasing an already released reservation is idempotent.",
        repair_instruction="Keep released reservations excluded from unavailable funds exactly once.",
    )
    assert_decimal_equal(
        engine.spent_balance("acct_1"),
        Decimal("0"),
        behavior="Idempotent release must not affect spent balance.",
        spec="AGENTS.md Domain Rule 10: releasing an already released reservation is idempotent.",
        repair_instruction="Do not count released reservations as spent.",
    )


def test_invalid_state_transitions_and_missing_reservations_fail_without_mutating_balances() -> None:
    engine = new_engine()
    create_account(engine)
    assert_success(
        engine.reserve("acct_1", "committed_res", Decimal("30")),
        behavior="A valid reservation must be creatable before committed transition checks.",
        spec="AGENTS.md Domain Rule 1: a reservation may be created only if amount <= available_balance.",
        expected="`reserve('acct_1', 'committed_res', Decimal('30'))` returns success=True.",
        repair_instruction="Create valid active reservations before commit.",
    )
    assert_success(
        engine.commit("committed_res"),
        behavior="A valid reservation must be committable before committed transition checks.",
        spec="AGENTS.md Domain Rule 5: committing an active reservation increases spent balance.",
        expected="`commit('committed_res')` returns success=True.",
        repair_instruction="Allow active reservations to transition to committed.",
    )

    assert_failure(
        engine.release("committed_res"),
        behavior="A committed reservation cannot be released.",
        spec="AGENTS.md Domain Rule 11: a committed reservation cannot be released.",
        expected="`release('committed_res')` returns success=False.",
        repair_instruction="Reject release attempts for committed reservations without changing balances.",
    )

    assert_success(
        engine.reserve("acct_1", "released_res", Decimal("20")),
        behavior="A valid reservation must be creatable before released transition checks.",
        spec="AGENTS.md Domain Rule 1: a reservation may be created only if amount <= available_balance.",
        expected="`reserve('acct_1', 'released_res', Decimal('20'))` returns success=True.",
        repair_instruction="Create valid active reservations before release.",
    )
    assert_success(
        engine.release("released_res"),
        behavior="A valid reservation must be releasable before released transition checks.",
        spec="AGENTS.md Domain Rule 6: releasing an active reservation restores available balance.",
        expected="`release('released_res')` returns success=True.",
        repair_instruction="Allow active reservations to transition to released.",
    )

    assert_failure(
        engine.commit("released_res"),
        behavior="A released reservation cannot be committed.",
        spec="AGENTS.md Domain Rule 12: a released reservation cannot be committed.",
        expected="`commit('released_res')` returns success=False.",
        repair_instruction="Reject commit attempts for released reservations without changing balances.",
    )
    assert_failure(
        engine.commit("missing_res"),
        behavior="Committing a non-existent reservation must fail.",
        spec="AGENTS.md Domain Rule 7: committing a non-existent reservation fails.",
        expected="`commit('missing_res')` returns success=False.",
        repair_instruction="Return an explicit failure result when commit cannot find the reservation.",
    )
    assert_failure(
        engine.release("missing_res"),
        behavior="Releasing a non-existent reservation must fail.",
        spec="AGENTS.md Domain Rule 8: releasing a non-existent reservation fails.",
        expected="`release('missing_res')` returns success=False.",
        repair_instruction="Return an explicit failure result when release cannot find the reservation.",
    )

    assert_decimal_equal(
        engine.available_balance("acct_1"),
        Decimal("70"),
        behavior="Invalid state transitions must not mutate available balance.",
        spec=(
            "AGENTS.md Domain Rules 11 and 12: committed reservations cannot be "
            "released and released reservations cannot be committed."
        ),
        repair_instruction=(
            "Leave reservation state and balance calculations unchanged after "
            "invalid transition attempts."
        ),
    )
    assert_decimal_equal(
        engine.spent_balance("acct_1"),
        Decimal("30"),
        behavior="Invalid state transitions must not mutate spent balance.",
        spec=(
            "AGENTS.md Domain Rules 11 and 12: committed reservations cannot be "
            "released and released reservations cannot be committed."
        ),
        repair_instruction="Do not change committed spend after invalid transition attempts.",
    )
