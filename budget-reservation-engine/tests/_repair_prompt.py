import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
FAILURE_PATH = REPO_ROOT / "failures" / "latest_failure.md"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def write_repair_prompt(
    *,
    failed_behavior: str,
    relevant_spec_section: str,
    expected_behavior: str,
    actual_behavior: str,
    repair_instruction: str,
) -> None:
    FAILURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FAILURE_PATH.write_text(
        "\n".join(
            [
                "# Repair Prompt",
                "",
                "You are fixing the Budget Reservation Engine implementation.",
                "",
                "## Failed behavior",
                "",
                failed_behavior,
                "",
                "## Relevant spec section",
                "",
                relevant_spec_section,
                "",
                "## Expected behavior",
                "",
                expected_behavior,
                "",
                "## Actual behavior",
                "",
                actual_behavior,
                "",
                "## Repair instruction",
                "",
                repair_instruction,
                "",
                "## Constraints",
                "",
                "- Modify implementation code only.",
                "- Do not modify tests.",
                "- Do not weaken or reinterpret Spec 001.",
                "- Do not add Redis, database, API, async worker, or persistence behavior.",
                "- Keep all Spec 001 storage in process memory.",
                "- Use Decimal for money values, not float.",
                "- Do not rely on module-level global dictionaries for account or reservation state.",
                "",
            ]
        ),
        encoding="utf-8",
    )