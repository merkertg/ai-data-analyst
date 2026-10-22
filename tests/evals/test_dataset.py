"""Pure dataset-identity checks: verified files, typed values and streamed SQL."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.data.generate import FIELDS, DataRow
from app.data.load import _read_export
from app.evals.__main__ import check_database_matches


def database_rows(
    monkeypatch: pytest.MonkeyPatch, tables: dict[str, list[DataRow]]
) -> MagicMock:
    """Replace only SQL I/O, returning typed rows in primary-key order."""
    factory = MagicMock()
    session = factory.return_value.__enter__.return_value

    def execute(query: Any) -> MagicMock:
        """Stand in for a streaming Result context manager."""
        name = query.get_final_froms()[0].name
        result = MagicMock()
        result.__enter__.return_value = result
        result.mappings.return_value = iter(
            sorted(tables[name], key=lambda row: int(str(row["id"])))
        )
        return result

    session.execute.side_effect = execute
    monkeypatch.setattr("app.evals.__main__.LazySession", factory)
    return factory


def test_all_six_tables_stream_in_one_read_only_session(
    verified_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inventory is included; primary-key order and bounded fetches are explicit."""
    tables = _read_export(verified_bundle)
    for rows in tables.values():
        rows.reverse()
    factory = database_rows(monkeypatch, tables)

    check_database_matches(verified_bundle)

    factory.assert_called_once_with(read_only=True)
    queries = [
        call.args[0]
        for call in factory.return_value.__enter__.return_value.execute.call_args_list
    ]
    assert [query.get_final_froms()[0].name for query in queries] == list(FIELDS)
    assert all(query.get_execution_options()["yield_per"] == 1000 for query in queries)
    assert all(
        str(query).endswith("ORDER BY " + query.get_final_froms()[0].name + ".id")
        for query in queries
    )


@pytest.mark.parametrize(
    ("name", "field", "replacement"),
    [
        ("customers", "name", "A different customer"),
        ("products", "cost", Decimal("70000.01")),
        ("orders", "status", "pending"),
        ("order_items", "unit_price", Decimal("100000.01")),
        ("refunds", "amount", Decimal("1000.01")),
        ("inventory_snapshots", "quantity", 1),
    ],
)
def test_equal_counts_cannot_hide_different_values(
    verified_bundle: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    field: str,
    replacement: Any,
) -> None:
    """One altered value in any domain table invalidates the evaluation setup."""
    tables = _read_export(verified_bundle)
    tables[name][0][field] = replacement
    database_rows(monkeypatch, tables)

    with pytest.raises(ValueError, match=f"^{name}: database content differs"):
        check_database_matches(verified_bundle)


@pytest.mark.parametrize("extra", [False, True], ids=["missing-row", "extra-row"])
def test_inventory_row_count_must_match(
    verified_bundle: Path, monkeypatch: pytest.MonkeyPatch, extra: bool
) -> None:
    """A stream ending early or continuing past the CSV is rejected."""
    tables = _read_export(verified_bundle)
    rows = tables["inventory_snapshots"]
    if extra:
        rows.append(rows[-1] | {"id": 999})
    else:
        rows.pop()
    database_rows(monkeypatch, tables)

    with pytest.raises(ValueError, match="^inventory_snapshots:"):
        check_database_matches(verified_bundle)


def test_equivalent_decimal_scales_and_timestamp_zones_match(
    verified_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Formatting differences are not changes to money or an absolute instant."""
    tables = deepcopy(_read_export(verified_bundle))
    tables["products"][0]["cost"] = Decimal("70000.0000")
    for row in tables["orders"]:
        for field in ("ordered_at", "paid_at"):
            if isinstance(stamp := row[field], datetime):
                row[field] = stamp.astimezone(UTC)
    database_rows(monkeypatch, tables)

    check_database_matches(verified_bundle)


def test_different_instant_is_not_a_timezone_format_difference(
    verified_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An actual one-second payment change is still a mismatch."""
    tables = _read_export(verified_bundle)
    stamp = tables["orders"][0]["paid_at"]
    assert isinstance(stamp, datetime)
    tables["orders"][0]["paid_at"] = stamp + timedelta(seconds=1)
    database_rows(monkeypatch, tables)

    with pytest.raises(ValueError, match="^orders:"):
        check_database_matches(verified_bundle)


@pytest.mark.parametrize("missing", [False, True], ids=["bad-hash", "missing-file"])
def test_export_validation_finishes_before_any_sql(
    verified_bundle: Path, monkeypatch: pytest.MonkeyPatch, missing: bool
) -> None:
    """Corrupt or absent inventory is rejected before even opening a session."""
    factory = database_rows(monkeypatch, {})
    stock = verified_bundle / "inventory_snapshots.csv"
    if missing:
        stock.unlink()
    else:
        stock.write_text(stock.read_text() + "999,1,2026-09-30,99\n")

    with pytest.raises((ValueError, OSError)):
        check_database_matches(verified_bundle)

    factory.assert_not_called()
