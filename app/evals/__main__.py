"""Run the agent evals against the database in DATABASE_URL.

    uv run python -m app.evals --bundle data/demo --provider reference
    uv run python -m app.evals --bundle data/demo --provider mock --output mock.json
    uv run python -m app.evals --bundle data/demo --provider openai --output gpt.json

The database must contain exactly the verified bundle that the oracle reads:
all six tables are compared before any question is asked. Runs are scored in memory
and never stored in agent_runs. The openai provider sends every question,
tool result and report to the API and costs money.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.agents.mock import MockProvider
from app.agents.tools import ToolExecutor
from app.api.dependencies import LazySession
from app.data.generate import FIELDS
from app.data.load import _read_export
from app.db.base import Base
from app.db.session import DatabaseNotConfigured
from app.evals.cases import CASES_FILE, EvalCase, load_cases
from app.evals.oracle import Oracle
from app.evals.reference import ReferenceProvider
from app.evals.runner import ProviderForCase, run_all
from app.llm.config import get_llm_settings
from app.llm.errors import LLMError
from app.llm.openai_provider import OpenAIProvider


def check_database_matches(bundle: Path) -> None:
    """Compare every typed value of all six verified CSV files with one snapshot.

    The loader is reused only to validate and parse the export, never to compute
    expected metrics. Native Decimal, date and aware datetime equality accepts
    equivalent scales and time zones. SQL rows stream in bounded batches, while
    primary-key ordering makes CSV row order irrelevant.
    """
    tables = _read_export(bundle)
    with LazySession(read_only=True) as session:
        for name, fields in FIELDS.items():
            expected = sorted(tables[name], key=lambda row: int(str(row["id"])))
            table = Base.metadata.tables[name]
            query = (
                select(*(table.c[field] for field in fields))
                .order_by(table.c.id)
                .execution_options(yield_per=1000)
            )
            count = 0
            with session.execute(query) as result:
                for actual in result.mappings():
                    if count >= len(expected) or any(
                        actual[field] != expected[count][field] for field in fields
                    ):
                        raise ValueError(
                            f"{name}: database content differs from bundle"
                        )
                    count += 1
            if count != len(expected):
                raise ValueError(f"{name}: database content differs from bundle")


def provider_factory(name: str) -> ProviderForCase:
    """A provider per case; OpenAI needs a key and a model in .env."""
    if name == "reference":
        return ReferenceProvider
    if name == "mock":
        return lambda _: MockProvider()
    provider = OpenAIProvider(get_llm_settings())
    return lambda _: provider


def table(report: dict[str, object]) -> str:
    """A short per-case table for the terminal."""
    lines = ["case  kind          pass  ms     notes"]
    for case in report["cases"]:  # type: ignore[attr-defined]
        notes = "; ".join(case["notes"])[:80]
        passed = "yes" if case["passed"] else "no"
        lines.append(
            f"{case['id']}   {case['kind']:<12}  {passed:<4}  "
            f"{case['latency_ms']:<5}  {notes}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run all cases with one provider and print or save the scored report."""
    parser = argparse.ArgumentParser(prog="python -m app.evals", description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=CASES_FILE)
    parser.add_argument(
        "--provider", choices=["reference", "mock", "openai"], required=True
    )
    parser.add_argument("--output", type=Path, help="write the full JSON report")
    parser.add_argument("--only", nargs="*", help="run only these case ids")
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise FileExistsError("the output file already exists")
        cases: list[EvalCase] = load_cases(args.cases)
        if args.only:
            cases = [case for case in cases if case.id in set(args.only)]
        check_database_matches(args.bundle)
        oracle = Oracle(args.bundle)
        settings = get_llm_settings()
        tools = ToolExecutor(partial(LazySession, read_only=True))
        report = run_all(
            cases, provider_factory(args.provider), tools, settings, oracle
        )
        report["provider"] = args.provider
    except (ValueError, ValidationError, OSError, ArithmeticError) as error:
        print(f"Eval setup failed: {error}", file=sys.stderr)
        return 2
    except (DatabaseNotConfigured, SQLAlchemyError, LLMError):
        print(
            "Eval failed: check DATABASE_URL, migrations and LLM settings.",
            file=sys.stderr,
        )
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
    print(table(report))
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
