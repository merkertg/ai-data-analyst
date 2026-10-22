"""All eval questions on the full seed-42 dataset, in the *_test database.

The reference run must pass every case: that proves each question is
answerable with the tools and that the SQL tools agree with the independent
Pandas oracle. The mock run is a regression baseline: the set of questions
it passes is recorded and must not change silently.
"""

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.agents.mock import MockProvider
from app.agents.tools import ToolExecutor
from app.data.generate import export_dataset, generate_dataset
from app.data.load import load_dataset
from app.evals.cases import load_cases
from app.evals.oracle import Oracle
from app.evals.reference import ReferenceProvider
from app.evals.runner import run_all
from app.llm.config import LLMSettings

# Questions the keyword-based demo provider answers correctly (17 of 42).
MOCK_BASELINE = {
    "M01", "M07", "C01", "C02", "C05", "G02", "G03", "G04", "G05",
    "G06", "G07", "R01", "R02", "R03", "S01", "S02", "X04",
}  # fmt: skip
SETTINGS = LLMSettings(_env_file=None)


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The default demo bundle: seed 42, 20 000 orders."""
    directory = tmp_path_factory.mktemp("demo") / "bundle"
    export_dataset(generate_dataset(seed=42), directory)
    return directory


@pytest.fixture
def tools(db_session: Session, bundle: Path) -> ToolExecutor:
    """The bundle loaded into the rolled-back test transaction."""
    load_dataset(db_session, bundle)

    def sessions() -> AbstractContextManager[Session]:
        return nullcontext(db_session)

    return ToolExecutor(sessions)


def test_reference_run_passes_every_case(tools: ToolExecutor, bundle: Path) -> None:
    """SQL tools and the Pandas oracle agree on all questions."""
    report = run_all(load_cases(), ReferenceProvider, tools, SETTINGS, Oracle(bundle))

    failed = [case["id"] for case in report["cases"] if not case["passed"]]
    assert failed == []
    assert report["summary"]["value_accuracy"] == 1.0


def test_mock_baseline_is_stable(tools: ToolExecutor, bundle: Path) -> None:
    """The demo provider passes exactly the recorded questions."""
    report = run_all(
        load_cases(), lambda _: MockProvider(), tools, SETTINGS, Oracle(bundle)
    )

    passed = {case["id"] for case in report["cases"] if case["passed"]}
    assert passed == MOCK_BASELINE
    assert report["summary"]["completed_rate"] == 1.0
    # The demo provider never refuses: every refusal case fails, as recorded.
    assert report["summary"]["by_kind"]["refusal"] == {"passed": 0, "total": 3}
