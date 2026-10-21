"""Print an exact sales report from the configured PostgreSQL database."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.analytics.models import Dimension, Period
from app.analytics.service import (
    compare_periods,
    contributions,
    monthly_metrics,
    summarize,
)
from app.db.session import DatabaseNotConfigured, get_engine


def build_report(
    session: Session,
    period: Period,
    previous: Period | None = None,
    dimension: Dimension = "category",
) -> dict[str, object]:
    """Compose report objects; the caller provides a consistent read transaction."""
    return {
        "currency": "RUB",
        "timezone": "Europe/Moscow",
        "summary": summarize(session, period),
        "monthly": monthly_metrics(session, period),
        "comparison": compare_periods(session, period, previous) if previous else None,
        "dimension": dimension,
        "contributions": (
            contributions(session, period, previous, dimension) if previous else []
        ),
    }


def _json_default(value: object) -> object:
    """Keep decimals as text and dates as ISO strings in nested result models."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def main(argv: Sequence[str] | None = None) -> int:
    """Validate dates before connecting and run a read-only repeatable-read report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--compare-start", type=date.fromisoformat)
    parser.add_argument("--compare-end", type=date.fromisoformat)
    parser.add_argument(
        "--dimension", choices=("category", "region"), default="category"
    )
    args = parser.parse_args(argv)
    if (args.compare_start is None) != (args.compare_end is None):
        parser.error("--compare-start and --compare-end must be supplied together")
    try:
        period = Period(args.start, args.end)
        previous = (
            Period(args.compare_start, args.compare_end) if args.compare_start else None
        )
    except ValueError as error:
        parser.error(str(error))
    try:
        with get_engine().connect() as connection:
            connection = connection.execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True
            )
            with Session(bind=connection) as session:
                report = build_report(
                    session, period, previous, cast(Dimension, args.dimension)
                )
        rendered = json.dumps(report, default=_json_default, indent=2, sort_keys=True)
    except (DatabaseNotConfigured, SQLAlchemyError, ValueError, ArithmeticError):
        print(
            json.dumps(
                {
                    "error": (
                        "Analytics report failed; check database settings and periods."
                    )
                }
            ),
            file=sys.stderr,
        )
        return 1
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
