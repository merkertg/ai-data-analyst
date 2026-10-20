"""Generate fictional IndustrialFlow data without a database or external services."""

import argparse
import csv
import hashlib
import json
import random
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

type DataValue = str | int | Decimal | datetime | date | None
type DataRow = dict[str, DataValue]
type JsonValue = None | bool | int | str | list[JsonValue] | dict[str, JsonValue]

MOSCOW = ZoneInfo("Europe/Moscow")
START = date(2026, 1, 1)
END = date(2026, 9, 30)
CENT = Decimal("0.01")
REGIONS = (
    "Central",
    "Northwest",
    "South",
    "Volga",
    "Ural",
    "Siberia",
    "Far East",
    "Caucasus",
)
CATEGORIES = ("pumps", "compressors", "valves", "sensors")
FIELDS: dict[str, tuple[str, ...]] = {
    "customers": ("id", "name", "region", "industry"),
    "products": ("id", "sku", "name", "category", "cost"),
    "orders": ("id", "customer_id", "status", "ordered_at", "paid_at"),
    "order_items": (
        "id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
        "discount",
    ),
    "refunds": ("id", "order_item_id", "amount", "processed_at"),
    "inventory_snapshots": ("id", "product_id", "snapshot_date", "quantity"),
}


@dataclass
class DemoDataset:
    """Six insertion-ordered row sets and a separate evaluation-only truth file."""

    tables: dict[str, list[DataRow]]
    ground_truth: dict[str, JsonValue]


def money(value: Decimal) -> Decimal:
    """Round each line once using the same tie rule as PostgreSQL NUMERIC."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_amount(row: DataRow) -> Decimal:
    """Compute an exact discounted line total; no floating point is involved."""
    return money(
        Decimal(str(row["quantity"]))
        * Decimal(str(row["unit_price"]))
        * (1 - Decimal(str(row["discount"])))
    )


def generate_dataset(seed: int = 42, order_count: int = 20000) -> DemoDataset:
    """Build a seeded January–September dataset and inject five valid business events.

    Dates are spread across all 273 days before randomness is applied. Using
    integer random draws for money makes generation independent of binary floats.
    """
    if not 1000 <= order_count <= 100000:
        raise ValueError("orders must be between 1000 and 100000")
    rng = random.Random(seed)
    tables: dict[str, list[DataRow]] = {name: [] for name in FIELDS}
    for ident in range(1, 641):
        tables["customers"].append(
            {
                "id": ident,
                "name": f"Demo Industrial Customer {ident:04d}",
                "region": REGIONS[(ident - 1) % 8],
                "industry": ("manufacturing", "energy", "chemicals", "mining")[
                    (ident - 1) % 4
                ],
            }
        )
    for ident in range(1, 65):
        category = CATEGORIES[(ident - 1) // 16]
        base_cost = (30000, 60000, 3000, 500)[(ident - 1) // 16]
        cost = money(Decimal(base_cost) * Decimal(rng.randint(80, 120)) / 100)
        tables["products"].append(
            {
                "id": ident,
                "sku": f"IF-{ident:04d}",
                "name": f"Demo {category} {ident:02d}",
                "category": category,
                "cost": cost,
            }
        )
    for ident in range(1, order_count + 1):
        day = START + timedelta(days=(ident - 1) % 273)
        paid = datetime(
            day.year,
            day.month,
            day.day,
            rng.randint(8, 18),
            rng.randrange(60),
            tzinfo=MOSCOW,
        )
        status = rng.choices(("paid", "pending", "cancelled"), weights=(88, 7, 5))[0]
        order: DataRow = {
            "id": ident,
            "customer_id": rng.randint(1, 640),
            "status": status,
            "ordered_at": paid - timedelta(hours=rng.randint(1, 48)),
            "paid_at": paid if status == "paid" else None,
        }
        # Keep order creation inside the advertised data interval as well.
        order["ordered_at"] = max(
            paid - timedelta(hours=rng.randint(1, 24)),
            datetime(2026, 1, 1, tzinfo=MOSCOW),
        )
        tables["orders"].append(order)
        for product_id in rng.sample(range(1, 65), rng.randint(1, 3)):
            product = tables["products"][product_id - 1]
            price = money(
                Decimal(str(product["cost"])) * Decimal(rng.randint(125, 160)) / 100
            )
            tables["order_items"].append(
                {
                    "id": len(tables["order_items"]) + 1,
                    "order_id": ident,
                    "product_id": product_id,
                    "quantity": rng.randint(2, 8),
                    "unit_price": price,
                    "discount": rng.choice(
                        (Decimal("0.0000"), Decimal("0.0500"), Decimal("0.1000"))
                    ),
                }
            )
    # Reserve a paid June sensor sale for A05, including for small test datasets.
    reserved_order = tables["orders"][151]
    reserved_order["status"] = "paid"
    reserved_order["paid_at"] = datetime(2026, 6, 1, 12, tzinfo=MOSCOW)
    reserved_order["ordered_at"] = datetime(2026, 6, 1, 10, tzinfo=MOSCOW)
    reserved_item = next(row for row in tables["order_items"] if row["order_id"] == 152)
    # Replace the whole order's catalogue choice to preserve product uniqueness.
    for index, row in enumerate(
        row for row in tables["order_items"] if row["order_id"] == 152
    ):
        row["product_id"] = 49 + index
        row["unit_price"] = money(
            Decimal(str(tables["products"][48 + index]["cost"])) * Decimal("1.40")
        )
    # Reserve an eligible South/August/valve sale so A02 exists for every seed,
    # including the minimum supported dataset where random scope can be empty.
    discount_order = tables["orders"][212]
    discount_order["customer_id"] = 3
    discount_order["status"] = "paid"
    discount_order["paid_at"] = datetime(2026, 8, 1, 12, tzinfo=MOSCOW)
    discount_order["ordered_at"] = datetime(2026, 8, 1, 10, tzinfo=MOSCOW)
    for index, row in enumerate(
        row for row in tables["order_items"] if row["order_id"] == 213
    ):
        row["product_id"] = 33 + index
        row["unit_price"] = money(
            Decimal(str(tables["products"][32 + index]["cost"])) * Decimal("1.40")
        )
    # Reserve the remaining random scopes too; accepted seeds always contain
    # actual A01 and A03 events instead of a reference entry with zero rows.
    for order_id, month, first_product in ((244, 9, 1), (182, 7, 17)):
        scoped_order = tables["orders"][order_id - 1]
        scoped_order["status"] = "paid"
        scoped_order["paid_at"] = datetime(2026, month, 1, 12, tzinfo=MOSCOW)
        scoped_order["ordered_at"] = datetime(2026, month, 1, 10, tzinfo=MOSCOW)
        for index, row in enumerate(
            row for row in tables["order_items"] if row["order_id"] == order_id
        ):
            product_id = first_product + index
            row["product_id"] = product_id
            row["unit_price"] = money(
                Decimal(str(tables["products"][product_id - 1]["cost"]))
                * Decimal("1.40")
            )
    for offset in range(273):
        for product_id in range(1, 65):
            tables["inventory_snapshots"].append(
                {
                    "id": offset * 64 + product_id,
                    "product_id": product_id,
                    "snapshot_date": START + timedelta(days=offset),
                    "quantity": rng.randint(30, 120),
                }
            )
    for row in tables["order_items"]:
        order = tables["orders"][int(str(row["order_id"])) - 1]
        paid_at = order["paid_at"]
        if isinstance(paid_at, datetime) and rng.randrange(100) < 2:
            processed = min(
                paid_at + timedelta(days=rng.randint(1, 14)),
                datetime(2026, 9, 30, 23, 59, tzinfo=MOSCOW),
            )
            tables["refunds"].append(
                {
                    "id": len(tables["refunds"]) + 1,
                    "order_item_id": row["id"],
                    "amount": money(line_amount(row) * Decimal("0.10")),
                    "processed_at": processed,
                }
            )
    anomalies = _inject_anomalies(tables, reserved_item)
    truth: dict[str, JsonValue] = {
        "schema_version": 1,
        "seed": seed,
        "order_count": order_count,
        "currency": "RUB",
        "timezone": "Europe/Moscow",
        "period": {"start": START.isoformat(), "end": END.isoformat()},
        "anomalies": anomalies,
    }
    return DemoDataset(tables, truth)


def _inject_anomalies(
    tables: dict[str, list[DataRow]], reserved_item: DataRow
) -> list[JsonValue]:
    """Record observed changes against the same seeded rows before each injection.

    These are business anomalies, not integrity failures. A stockout and a sales
    drop can coexist; the injected truth does not assert a causal relationship.
    """
    anomalies: list[JsonValue] = []
    a01_before = a01_after = 0
    a02_before = a02_after = Decimal("0.00")
    a01_count = a02_count = 0
    compressor_lines: list[DataRow] = []
    for row in tables["order_items"]:
        order = tables["orders"][int(str(row["order_id"])) - 1]
        paid = order["paid_at"]
        if not isinstance(paid, datetime):
            continue
        product = tables["products"][int(str(row["product_id"])) - 1]
        customer = tables["customers"][int(str(order["customer_id"])) - 1]
        if paid.month == 9 and product["category"] == "pumps":
            before = int(str(row["quantity"]))
            a01_before += before
            row["quantity"] = max(1, before * 2 // 5)
            a01_after += int(str(row["quantity"]))
            a01_count += 1
        if (
            paid.month == 8
            and product["category"] == "valves"
            and customer["region"] == "South"
        ):
            a02_before += line_amount(row)
            row["discount"] = Decimal("0.3500")
            a02_after += line_amount(row)
            a02_count += 1
        if paid.month == 7 and product["category"] == "compressors":
            compressor_lines.append(row)
    anomalies.append(
        {
            "id": "A01",
            "kind": "pump_volume_drop",
            "period": "2026-09",
            "scope": "paid pump lines; quantity=max(1, floor(original*0.40))",
            "affected_rows": a01_count,
            "baseline_quantity": a01_before,
            "observed_quantity": a01_after,
        }
    )
    anomalies.append(
        {
            "id": "A02",
            "kind": "regional_discount",
            "period": "2026-08",
            "scope": "paid valve lines; South; discount=0.3500",
            "affected_rows": a02_count,
            "baseline_sales": str(a02_before),
            "observed_sales": str(a02_after),
        }
    )
    affected_ids = {row["id"] for row in compressor_lines}
    before_refunds = sum(
        (
            Decimal(str(row["amount"]))
            for row in tables["refunds"]
            if row["order_item_id"] in affected_ids
        ),
        Decimal("0.00"),
    )
    added_refunds = Decimal("0.00")
    for row in compressor_lines:
        order = tables["orders"][int(str(row["order_id"])) - 1]
        amount = money(line_amount(row) * Decimal("0.30"))
        added_refunds += amount
        tables["refunds"].append(
            {
                "id": len(tables["refunds"]) + 1,
                "order_item_id": row["id"],
                "amount": amount,
                "processed_at": order["paid_at"],
            }
        )
    anomalies.append(
        {
            "id": "A03",
            "kind": "compressor_refund_spike",
            "period": "2026-07",
            "scope": (
                "July paid compressor lines; extra refund=ROUND(line_total*0.30,2)"
            ),
            "affected_rows": len(compressor_lines),
            "baseline_refunds_for_lines": str(before_refunds),
            "observed_refunds_for_lines": str(before_refunds + added_refunds),
            "added_refunds": str(added_refunds),
        }
    )
    inventory_before = 0
    for row in tables["inventory_snapshots"]:
        snapshot = row["snapshot_date"]
        if (
            row["product_id"] == 1
            and isinstance(snapshot, date)
            and date(2026, 9, 10) <= snapshot <= date(2026, 9, 19)
        ):
            inventory_before += int(str(row["quantity"]))
            row["quantity"] = 0
    anomalies.append(
        {
            "id": "A04",
            "kind": "stockout",
            "period": "2026-09-10/2026-09-19",
            "product_id": 1,
            "affected_rows": 10,
            "baseline_quantity_sum": inventory_before,
            "observed_quantity_sum": 0,
        }
    )
    quantity_before = int(str(reserved_item["quantity"]))
    amount_before = line_amount(reserved_item)
    reserved_item["quantity"] = 500
    anomalies.append(
        {
            "id": "A05",
            "kind": "large_sensor_order",
            "period": "2026-06",
            "order_id": 152,
            "order_item_id": int(str(reserved_item["id"])),
            "baseline_quantity": quantity_before,
            "observed_quantity": 500,
            "baseline_sales": str(amount_before),
            "observed_sales": str(line_amount(reserved_item)),
        }
    )
    return anomalies


def _csv_value(value: DataValue) -> str:
    """Serialize dates, exact decimal values and nullable timestamps canonically."""
    if value is None:
        return ""
    return value.isoformat() if isinstance(value, (date, datetime)) else str(value)


def export_dataset(dataset: DemoDataset, output: Path) -> None:
    """Publish deterministic CSV files and hashes without overwriting user files."""
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output must be a new or empty directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".demo-", dir=output.parent) as temporary:
        staging = Path(temporary) / "dataset"
        staging.mkdir()
        files: dict[str, JsonValue] = {}
        for name, fields in FIELDS.items():
            path = staging / f"{name}.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream, lineterminator="\n")
                writer.writerow(fields)
                writer.writerows(
                    [_csv_value(row[field]) for field in fields]
                    for row in dataset.tables[name]
                )
            files[path.name] = {
                "rows": len(dataset.tables[name]),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        manifest: dict[str, JsonValue] = {
            "schema_version": 1,
            "seed": dataset.ground_truth["seed"],
            "files": files,
        }
        for name, payload in (
            ("ground_truth.json", dataset.ground_truth),
            ("manifest.json", manifest),
        ):
            (staging / name).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        if output.exists():
            output.rmdir()
        staging.replace(output)


def main() -> None:
    """Expose deterministic generation as a database-independent command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/demo"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--orders", type=int, default=20000)
    args = parser.parse_args()
    try:
        dataset = generate_dataset(seed=args.seed, order_count=args.orders)
        export_dataset(dataset, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Generation failed: {error}\n")
    print(
        json.dumps(
            {name: len(rows) for name, rows in dataset.tables.items()}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
