"""A hand-made CSV bundle shared by the oracle and scoring tests.

The rows mirror app/db/sample.py: September sales 310 000.00, refunds
1 000.00; October sales 18 000.00, refunds 500.00. Two extra lines check
rounding to kopecks and that unpaid orders and their refunds never count.
"""

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from app.evals.oracle import Oracle

SEP = (date(2026, 9, 1), date(2026, 10, 1))
OCT = (date(2026, 10, 1), date(2026, 11, 1))

TABLES: dict[str, list[tuple[str, ...]]] = {
    "customers": [
        ("id", "name", "region", "industry"),
        ("1", "North", "Северо-Запад", "metal"),
        ("2", "South", "Юг", "chemistry"),
    ],
    "products": [
        ("id", "sku", "name", "category", "cost"),
        ("1", "PMP-100", "Pump", "Насосы", "70000.00"),
        ("2", "SNS-020", "Sensor", "Датчики", "1200.00"),
        ("3", "VLV-050", "Valve", "Запорная арматура", "3000.00"),
    ],
    "orders": [
        ("id", "customer_id", "status", "ordered_at", "paid_at"),
        ("1", "1", "paid", "2026-09-03T10:00:00+03:00", "2026-09-05T12:00:00+03:00"),
        ("2", "2", "paid", "2026-09-18T15:00:00+03:00", "2026-09-20T09:30:00+03:00"),
        ("3", "2", "cancelled", "2026-09-25T11:00:00+03:00", ""),
        # Paid at 01:30 on 1 October in Moscow: still 30 September in UTC.
        ("5", "1", "paid", "2026-09-30T20:00:00+03:00", "2026-09-30T22:30:00+00:00"),
        ("6", "1", "paid", "2026-09-06T10:00:00+03:00", "2026-09-06T11:00:00+03:00"),
    ],
    "order_items": [
        ("id", "order_id", "product_id", "quantity", "unit_price", "discount"),
        ("1", "1", "1", "2", "100000.00", "0.1000"),
        ("2", "1", "2", "5", "2000.00", "0.0000"),
        ("3", "2", "1", "1", "120000.00", "0.0000"),
        ("4", "3", "3", "10", "4500.00", "0.0000"),
        ("5", "5", "3", "4", "4500.00", "0.0000"),
        # 3 × 333.33 × 0.9 = 899.991 → 899.99; 1 × 0.05 × 0.5 = 0.025 → 0.03.
        ("6", "6", "2", "3", "333.33", "0.1000"),
        ("7", "6", "3", "1", "0.05", "0.5000"),
    ],
    "refunds": [
        ("id", "order_item_id", "amount", "processed_at"),
        ("1", "2", "1000.00", "2026-09-10T11:00:00+03:00"),
        ("2", "2", "500.00", "2026-10-02T15:00:00+03:00"),
        # A refund of a cancelled order's line never reduces revenue.
        ("3", "4", "999.00", "2026-09-26T10:00:00+03:00"),
    ],
    "inventory_snapshots": [
        ("id", "product_id", "snapshot_date", "quantity"),
        ("1", "1", "2026-09-29", "0"),
        ("2", "1", "2026-09-30", "4"),
        ("3", "3", "2026-09-30", "0"),
    ],
}


def write_bundle(directory: Path) -> Path:
    """Write the six CSV files above into a directory."""
    for name, rows in TABLES.items():
        with (directory / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
    return directory


@pytest.fixture(scope="session")
def oracle(tmp_path_factory: pytest.TempPathFactory) -> Oracle:
    """The oracle reading the hand-made bundle."""
    return Oracle(write_bundle(tmp_path_factory.mktemp("bundle")))


@pytest.fixture
def verified_bundle(tmp_path: Path) -> Path:
    """The handwritten rows with the same manifest contract as a real export."""
    directory = write_bundle(tmp_path)
    manifest = {
        "schema_version": 1,
        "files": {
            f"{name}.csv": {
                "rows": len(rows) - 1,
                "sha256": hashlib.sha256(
                    (directory / f"{name}.csv").read_bytes()
                ).hexdigest(),
            }
            for name, rows in TABLES.items()
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory
