"""Read-only checks for business rules spanning several database rows.

PostgreSQL constraints validate individual rows and references. These checks
cover empty orders and the timing and cumulative value of their refunds.
Run with ``uv run python -m app.data.quality`` after loading a dataset.
"""

import json
import sys
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import DatabaseNotConfigured, get_engine

# A single statement gives every check the same PostgreSQL statement snapshot.
# Monetary calculations stay NUMERIC inside PostgreSQL, including line rounding.
QUALITY_SQL = """
SELECT 'empty_orders' AS name, COUNT(*) AS violations, 1 AS position
FROM orders AS o
WHERE NOT EXISTS (SELECT 1 FROM order_items AS i WHERE i.order_id = o.id)
UNION ALL
SELECT 'excessive_refunds', COUNT(*), 2
FROM order_items AS i
JOIN (
    SELECT order_item_id, SUM(amount) AS amount
    FROM refunds
    GROUP BY order_item_id
) AS r ON r.order_item_id = i.id
WHERE r.amount > ROUND(i.quantity * i.unit_price * (1 - i.discount), 2)
UNION ALL
SELECT 'refunds_on_unpaid_orders', COUNT(*), 3
FROM refunds AS r
JOIN order_items AS i ON i.id = r.order_item_id
JOIN orders AS o ON o.id = i.order_id
WHERE o.status <> 'paid'
UNION ALL
SELECT 'refunds_before_payment', COUNT(*), 4
FROM refunds AS r
JOIN order_items AS i ON i.id = r.order_item_id
JOIN orders AS o ON o.id = i.order_id
WHERE r.processed_at < o.paid_at
ORDER BY position
"""


@dataclass(frozen=True)
class QualityCheck:
    """A stable check name and the number of offending orders, lines or refunds."""

    name: str
    violations: int


@dataclass(frozen=True)
class QualityReport:
    """Ordered check results suitable for a command line or a saved manifest."""

    checks: tuple[QualityCheck, ...]

    @property
    def passed(self) -> bool:
        """Return whether every business rule has zero violations."""
        return all(check.violations == 0 for check in self.checks)

    def as_dict(self) -> dict[str, bool | list[dict[str, str | int]]]:
        """Return JSON-compatible values without database rows or secret settings."""
        return {
            "passed": self.passed,
            "checks": [
                {"name": check.name, "violations": check.violations}
                for check in self.checks
            ],
        }


def check_quality(session: Session) -> QualityReport:
    """Inspect persisted rows without flushing, committing or changing any data.

    ``empty_orders`` counts orders without lines. ``excessive_refunds`` counts
    lines whose combined refunds exceed the rounded discounted line amount.
    The two remaining checks count individual refund rows. A refund exactly at
    payment time and a refund exactly equal to the line amount are allowed.
    The caller must flush pending changes explicitly if they should be checked.
    """
    with session.no_autoflush:
        rows = session.execute(text(QUALITY_SQL)).mappings().all()
    return QualityReport(
        checks=tuple(
            QualityCheck(name=str(row["name"]), violations=int(row["violations"]))
            for row in rows
        )
    )


def main() -> int:
    """Print a JSON report and return 0 for passed checks, 1 otherwise.

    Connection and configuration errors deliberately omit exception details:
    driver and validation messages may contain database credentials.
    """
    try:
        with Session(get_engine()) as session:
            report = check_quality(session)
    except (DatabaseNotConfigured, SQLAlchemyError, ValueError):
        print(
            json.dumps({"error": "Data quality check could not access the database."}),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report.as_dict(), indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
