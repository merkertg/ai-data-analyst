"""Load a verified fictional CSV export into an empty migrated PostgreSQL database."""

import argparse
import csv
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Date, DateTime, Integer, Numeric, String, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401 -- register all domain tables in Base.metadata
from app.data.generate import FIELDS, DataRow, DataValue
from app.data.quality import check_quality
from app.db.base import Base
from app.db.session import DatabaseNotConfigured, get_engine


def _parse_value(value: str, column_type: object) -> DataValue:
    """Recover typed CSV values and reject non-finite money or naive timestamps."""
    if isinstance(column_type, DateTime):
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return parsed
    if isinstance(column_type, Date):
        return date.fromisoformat(value)
    if isinstance(column_type, Integer):
        return int(value)
    if isinstance(column_type, Numeric):
        amount = Decimal(value)
        if not amount.is_finite():
            raise ValueError("amounts must be finite decimals")
        scale = column_type.scale or 0
        if amount != amount.quantize(Decimal(1).scaleb(-scale)):
            raise ValueError("decimal precision exceeds the database column scale")
        return amount
    if isinstance(column_type, String):
        return value
    raise ValueError("unsupported column type")


def _read_export(directory: Path) -> dict[str, list[DataRow]]:
    """Verify six exact filenames, hashes, headers and row counts before any SQL.

    Evaluation labels are deliberately not read: importing data and querying the
    business database must work even when ground_truth.json is unavailable.
    """
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != {f"{name}.csv" for name in FIELDS}:
        raise ValueError("manifest must describe all six CSV files")
    tables: dict[str, list[DataRow]] = {}
    for name, fields in FIELDS.items():
        path = directory / f"{name}.csv"
        entry = files[path.name]
        if (
            not isinstance(entry, dict)
            or entry.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            raise ValueError(f"checksum mismatch: {path.name}")
        table = Base.metadata.tables[name]
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(fields):
                raise ValueError(f"invalid CSV header: {path.name}")
            rows: list[DataRow] = []
            for raw in reader:
                if set(raw) != set(fields) or any(
                    value is None for value in raw.values()
                ):
                    raise ValueError(f"invalid CSV row: {path.name}")
                rows.append(
                    {
                        field: _parse_value(raw[field], table.c[field].type)
                        for field in fields
                    }
                )
        if type(entry.get("rows")) is not int or len(rows) != entry["rows"]:
            raise ValueError(f"row count mismatch: {path.name}")
        tables[name] = rows
    return tables


def load_dataset(session: Session, directory: Path) -> dict[str, int]:
    """Insert all six verified row sets; the caller controls commit and rollback.

    A table lock serializes imports and ordinary writers before the emptiness
    check, so two concurrent loaders cannot both decide the database is empty.
    A savepoint removes all inserted rows on any validation failure, including
    when an embedding caller catches the exception and later commits.
    """
    tables = _read_export(directory)
    with session.begin_nested():
        session.execute(
            text("LOCK TABLE " + ", ".join(FIELDS) + " IN SHARE ROW EXCLUSIVE MODE")
        )
        if any(
            session.scalar(select(Base.metadata.tables[name].c.id).limit(1)) is not None
            for name in FIELDS
        ):
            raise ValueError(
                "all six domain tables must be empty; existing data is preserved"
            )
        for name, rows in tables.items():
            table = Base.metadata.tables[name]
            for offset in range(0, len(rows), 1000):
                session.execute(table.insert(), rows[offset : offset + 1000])
        if not check_quality(session).passed:
            raise ValueError("imported data failed cross-table quality checks")
        for name, rows in tables.items():
            # ALTER SEQUENCE is transactional; setval would survive a rollback.
            next_id = max((int(str(row["id"])) for row in rows), default=0) + 1
            session.execute(
                text(f"ALTER SEQUENCE {name}_id_seq RESTART WITH {next_id}")
            )
    return {name: len(rows) for name, rows in tables.items()}


def main() -> None:
    """Load the configured database atomically without leaking connection details."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/demo"))
    args = parser.parse_args()
    try:
        with Session(get_engine()) as session, session.begin():
            counts = load_dataset(session, args.input)
    except (
        OSError,
        ValueError,
        ArithmeticError,
        SQLAlchemyError,
        DatabaseNotConfigured,
    ):
        parser.exit(
            1,
            "Import failed: verify the export, database configuration, "
            "migrations and empty tables.\n",
        )
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
