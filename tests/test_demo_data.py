"""The synthetic sales dataset is reproducible, exact and internally consistent."""

import csv
import hashlib
import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.data.generate import (
    DataRow,
    DemoDataset,
    JsonValue,
    export_dataset,
    generate_dataset,
)

TABLE_NAMES = {
    "customers",
    "products",
    "orders",
    "order_items",
    "refunds",
    "inventory_snapshots",
}
MOSCOW = ZoneInfo("Europe/Moscow")
PERIOD_START = datetime(2026, 1, 1, tzinfo=MOSCOW)
PERIOD_END = datetime(2026, 10, 1, tzinfo=MOSCOW)


@pytest.fixture(scope="module")
def dataset() -> DemoDataset:
    """Build the advertised default dataset once for the structural checks."""
    return generate_dataset()


@pytest.fixture(scope="module")
def small_dataset() -> DemoDataset:
    """Keep repeat generation and filesystem checks reasonably small."""
    return generate_dataset(seed=123, order_count=1_000)


def scenarios_by_id(dataset: DemoDataset) -> dict[str, dict[str, JsonValue]]:
    """Validate the JSON scenario shape before inspecting reference values."""
    anomalies = dataset.ground_truth["anomalies"]
    assert isinstance(anomalies, list)
    result: dict[str, dict[str, JsonValue]] = {}
    for scenario in anomalies:
        assert isinstance(scenario, dict)
        identifier = scenario["id"]
        assert isinstance(identifier, str)
        assert identifier not in result
        result[identifier] = scenario
    return result


def paid_lines(
    dataset: DemoDataset, month: int, category: str, region: str | None = None
) -> list[DataRow]:
    """Select business scopes by joining IDs independently of the generator."""
    orders = {row["id"]: row for row in dataset.tables["orders"]}
    products = {row["id"]: row for row in dataset.tables["products"]}
    customers = {row["id"]: row for row in dataset.tables["customers"]}
    selected: list[DataRow] = []
    for row in dataset.tables["order_items"]:
        order = orders[row["order_id"]]
        paid_at = order["paid_at"]
        if order["status"] != "paid" or not isinstance(paid_at, datetime):
            continue
        if paid_at.astimezone(MOSCOW).month != month:
            continue
        if products[row["product_id"]]["category"] != category:
            continue
        if region is not None and customers[order["customer_id"]]["region"] != region:
            continue
        selected.append(row)
    return selected


def sales_total(rows: list[DataRow]) -> Decimal:
    """Recompute exact line-rounded sales for checking the exported reference."""
    return sum(
        (
            (
                Decimal(str(row["quantity"]))
                * Decimal(str(row["unit_price"]))
                * (1 - Decimal(str(row["discount"])))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for row in rows
        ),
        Decimal("0.00"),
    )


def test_default_dimensions_and_scenarios(dataset: DemoDataset) -> None:
    """The default size and five announced scenarios are part of the public API."""
    assert set(dataset.tables) == TABLE_NAMES
    assert all(dataset.tables.values())
    assert len(dataset.tables["customers"]) == 640
    assert len(dataset.tables["products"]) == 64
    assert len(dataset.tables["orders"]) == 20_000
    assert len({row["region"] for row in dataset.tables["customers"]}) == 8
    assert set(scenarios_by_id(dataset)) == {
        "A01",
        "A02",
        "A03",
        "A04",
        "A05",
    }
    # The reference file must be usable by tools without a custom JSON encoder.
    json.dumps(dataset.ground_truth, allow_nan=False)


def test_same_seed_reproduces_data_and_reference(small_dataset: DemoDataset) -> None:
    """A repeated request must reproduce both sales and the ground truth."""
    repeated = generate_dataset(seed=123, order_count=1_000)

    assert repeated.tables == small_dataset.tables
    assert repeated.ground_truth == small_dataset.ground_truth


def test_different_seed_changes_sales(small_dataset: DemoDataset) -> None:
    """The seed controls the underlying transactions, not just metadata."""
    different = generate_dataset(seed=124, order_count=1_000)

    assert different.tables["orders"] != small_dataset.tables["orders"]
    assert different.tables["order_items"] != small_dataset.tables["order_items"]


@pytest.mark.parametrize("seed", [42, 100, 123])
def test_minimum_dataset_has_records_for_every_anomaly(seed: int) -> None:
    """Even small exports retain the paid lines required by all sales scenarios."""
    scenarios = scenarios_by_id(generate_dataset(seed=seed, order_count=1_000))

    for identifier in ("A01", "A02", "A03"):
        affected_rows = scenarios[identifier]["affected_rows"]
        assert isinstance(affected_rows, int)
        assert affected_rows > 0, f"{identifier} has no affected rows for seed {seed}"


@pytest.mark.parametrize("order_count", [0, 999, 100_001])
def test_order_count_outside_supported_range_is_rejected(order_count: int) -> None:
    """Unsupported sizes fail before generation rather than weakening scenarios."""
    with pytest.raises(ValueError):
        generate_dataset(order_count=order_count)


@pytest.mark.parametrize(
    ("table", "field", "scale"),
    [
        ("products", "cost", -2),
        ("order_items", "unit_price", -2),
        ("order_items", "discount", -4),
        ("refunds", "amount", -2),
    ],
)
def test_financial_values_are_exact_decimals(
    dataset: DemoDataset, table: str, field: str, scale: int
) -> None:
    """Money has two decimal places; discount rates retain four places."""
    for row in dataset.tables[table]:
        value = row[field]
        assert isinstance(value, Decimal)
        assert value.is_finite()
        assert value.as_tuple().exponent == scale


def test_rows_have_valid_identifiers_and_references(dataset: DemoDataset) -> None:
    """All foreign keys resolve and each order has unique product lines."""
    identifiers: dict[str, set[int]] = {}
    for name, rows in dataset.tables.items():
        ids: set[int] = set()
        for row in rows:
            value = row["id"]
            assert isinstance(value, int) and value > 0
            ids.add(value)
            assert not any(isinstance(value, float) for value in row.values())
        assert len(ids) == len(rows)
        identifiers[name] = ids

    for row in dataset.tables["orders"]:
        assert row["customer_id"] in identifiers["customers"]
    pairs: set[tuple[object, object]] = set()
    orders_with_items: set[object] = set()
    for row in dataset.tables["order_items"]:
        assert row["order_id"] in identifiers["orders"]
        assert row["product_id"] in identifiers["products"]
        pair = (row["order_id"], row["product_id"])
        assert pair not in pairs
        pairs.add(pair)
        orders_with_items.add(row["order_id"])
        assert isinstance(row["quantity"], int) and row["quantity"] > 0
    assert orders_with_items == identifiers["orders"]
    for row in dataset.tables["refunds"]:
        assert row["order_item_id"] in identifiers["order_items"]
    for row in dataset.tables["inventory_snapshots"]:
        assert row["product_id"] in identifiers["products"]


def test_timestamps_and_snapshots_stay_in_reporting_period(
    dataset: DemoDataset,
) -> None:
    """Aware timestamps, statuses and snapshots obey the declared Moscow period."""
    for row in dataset.tables["orders"]:
        ordered_at = row["ordered_at"]
        paid_at = row["paid_at"]
        assert isinstance(ordered_at, datetime)
        assert ordered_at.utcoffset() is not None
        assert PERIOD_START <= ordered_at < PERIOD_END
        assert row["status"] in {"paid", "pending", "cancelled"}
        if row["status"] == "paid":
            assert isinstance(paid_at, datetime)
            assert paid_at.utcoffset() is not None
            assert ordered_at <= paid_at < PERIOD_END
        else:
            assert paid_at is None
    for row in dataset.tables["refunds"]:
        processed_at = row["processed_at"]
        assert isinstance(processed_at, datetime)
        assert processed_at.utcoffset() is not None
        assert PERIOD_START <= processed_at < PERIOD_END
    snapshots: set[tuple[object, object]] = set()
    for row in dataset.tables["inventory_snapshots"]:
        snapshot_date = row["snapshot_date"]
        assert isinstance(snapshot_date, date)
        assert date(2026, 1, 1) <= snapshot_date <= date(2026, 9, 30)
        key = (row["product_id"], snapshot_date)
        assert key not in snapshots
        snapshots.add(key)


def test_ground_truth_matches_observed_business_events(dataset: DemoDataset) -> None:
    """Each scenario identifies real records and reproducible financial evidence."""
    scenarios = scenarios_by_id(dataset)
    pumps = paid_lines(dataset, 9, "pumps")
    a01 = scenarios["A01"]
    assert len(pumps) == a01["affected_rows"]
    assert sum(int(str(row["quantity"])) for row in pumps) == a01["observed_quantity"]
    assert Decimal(str(a01["baseline_quantity"])) > Decimal(
        str(a01["observed_quantity"])
    )

    valves = paid_lines(dataset, 8, "valves", "South")
    a02 = scenarios["A02"]
    assert len(valves) == a02["affected_rows"]
    assert valves and all(row["discount"] == Decimal("0.3500") for row in valves)
    assert sales_total(valves) == Decimal(str(a02["observed_sales"]))
    assert Decimal(str(a02["baseline_sales"])) > sales_total(valves)

    compressors = paid_lines(dataset, 7, "compressors")
    compressor_ids = {row["id"] for row in compressors}
    a03 = scenarios["A03"]
    assert len(compressors) == a03["affected_rows"]
    actual_refunds = sum(
        (
            Decimal(str(row["amount"]))
            for row in dataset.tables["refunds"]
            if row["order_item_id"] in compressor_ids
        ),
        Decimal("0.00"),
    )
    assert actual_refunds == Decimal(str(a03["observed_refunds_for_lines"]))
    assert actual_refunds == Decimal(str(a03["baseline_refunds_for_lines"])) + Decimal(
        str(a03["added_refunds"])
    )
    assert Decimal(str(a03["added_refunds"])) > 0

    a04 = scenarios["A04"]
    stockout = []
    for row in dataset.tables["inventory_snapshots"]:
        snapshot_date = row["snapshot_date"]
        assert isinstance(snapshot_date, date)
        if row["product_id"] == a04["product_id"] and date(
            2026, 9, 10
        ) <= snapshot_date <= date(2026, 9, 19):
            stockout.append(row)
    assert len(stockout) == a04["affected_rows"] == 10
    assert all(row["quantity"] == 0 for row in stockout)
    assert a04["observed_quantity_sum"] == 0
    assert Decimal(str(a04["baseline_quantity_sum"])) > 0

    a05 = scenarios["A05"]
    sensor_order = next(
        row
        for row in dataset.tables["order_items"]
        if row["id"] == a05["order_item_id"]
    )
    assert sensor_order["order_id"] == a05["order_id"]
    assert sensor_order["quantity"] == a05["observed_quantity"] == 500
    assert sensor_order in paid_lines(dataset, 6, "sensors")
    assert sales_total([sensor_order]) == Decimal(str(a05["observed_sales"]))
    assert Decimal(str(a05["baseline_sales"])) < sales_total([sensor_order])


def test_export_is_complete_and_byte_reproducible(
    small_dataset: DemoDataset, tmp_path: Path
) -> None:
    """Repeated exports produce the same CSV and JSON bytes, including metadata."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    export_dataset(small_dataset, first)
    export_dataset(small_dataset, second)

    expected = {f"{name}.csv" for name in TABLE_NAMES} | {
        "ground_truth.json",
        "manifest.json",
    }
    assert {path.name for path in first.iterdir()} == expected
    assert {path.name for path in second.iterdir()} == expected
    for name in expected:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    for table, rows in small_dataset.tables.items():
        with (first / f"{table}.csv").open(newline="", encoding="utf-8") as source:
            exported = list(csv.DictReader(source))
        assert len(exported) == len(rows)
        assert set(exported[0]) == set(rows[0])
    assert json.loads((first / "ground_truth.json").read_text("utf-8")) == (
        small_dataset.ground_truth
    )
    manifest = json.loads((first / "manifest.json").read_text("utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["seed"] == small_dataset.ground_truth["seed"]
    assert set(manifest["files"]) == {f"{name}.csv" for name in TABLE_NAMES}
    for table, rows in small_dataset.tables.items():
        filename = f"{table}.csv"
        entry = manifest["files"][filename]
        assert entry["rows"] == len(rows)
        assert (
            entry["sha256"]
            == hashlib.sha256((first / filename).read_bytes()).hexdigest()
        )


def test_export_refuses_existing_nonempty_directory(
    small_dataset: DemoDataset, tmp_path: Path
) -> None:
    """An existing file survives a rejected export unchanged."""
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("keep this file", encoding="utf-8")

    with pytest.raises(ValueError):
        export_dataset(small_dataset, tmp_path)

    assert sentinel.read_text("utf-8") == "keep this file"
    assert list(tmp_path.iterdir()) == [sentinel]
