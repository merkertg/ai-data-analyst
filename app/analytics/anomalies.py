"""Find exploratory statistical and Isolation Forest signals without answer keys."""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.analytics.__main__ import _json_default
from app.analytics.anomaly_features import read_features
from app.analytics.detection import (
    detect_monthly,
    detect_quantities,
    detect_stockouts,
    isolation_findings,
)
from app.analytics.models import Period
from app.db.session import DatabaseNotConfigured, get_engine


def build_anomaly_report(
    session: Session, period: Period, seed: int = 42
) -> dict[str, object]:
    """Combine explainable rules and an exploratory forest on persisted features."""
    features = read_features(session, period)
    findings = [
        *detect_monthly(features.monthly),
        *detect_quantities(features.lines),
        *detect_stockouts(features.stock),
        *isolation_findings(features.monthly, seed=seed),
    ]
    findings.sort(key=lambda item: (item.method, item.period.start, item.kind, item.id))
    return {
        "schema_version": 1,
        "period": period,
        "seed": seed,
        "observations": {
            "monthly": len(features.monthly),
            "lines": len(features.lines),
            "stock": len(features.stock),
        },
        "configuration": {
            "min_history": 6,
            "robust_z_threshold": "6",
            "iqr_multiplier": "3",
            "min_zero_stock_days": 3,
            "isolation_trees": 100,
            "isolation_contamination": "auto",
        },
        "finding_count": len(findings),
        "findings": findings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Read one repeatable-read snapshot, then publish JSON to stdout or a new file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        period = Period(args.start, args.end)
        if not 0 <= args.seed <= 2**32 - 1:
            raise ValueError("seed must be between 0 and 4294967295")
        months = (period.end.year - period.start.year) * 12
        months += period.end.month - period.start.month + (period.end.day > 1)
        if months > 120:
            raise ValueError("at most 120 calendar months are supported")
    except ValueError as error:
        parser.error(str(error))
    try:
        if args.output and args.output.exists():
            raise FileExistsError("output exists")
        with get_engine().connect() as connection:
            connection = connection.execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True
            )
            with Session(bind=connection) as session:
                report = build_anomaly_report(session, period, args.seed)
        rendered = json.dumps(report, default=_json_default, indent=2, sort_keys=True)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(rendered + "\n")
        else:
            print(rendered)
    except (
        DatabaseNotConfigured,
        SQLAlchemyError,
        OSError,
        ValueError,
        ArithmeticError,
    ):
        print(
            json.dumps(
                {"error": "Detection failed; check database, dates and output."}
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
