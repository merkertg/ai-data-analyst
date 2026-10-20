"""CSV imports stay atomic and pass business checks on the isolated test database."""

import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.generate import export_dataset, generate_dataset
from app.data.load import load_dataset
from app.data.quality import check_quality
from app.db.base import Base
from app.db.models import Product


@pytest.fixture(scope="module")
def dataset_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Export one small, complete dataset without using DATABASE_URL or .env."""
    directory = tmp_path_factory.mktemp("demo-data") / "export"
    export_dataset(generate_dataset(seed=123, order_count=1_000), directory)
    return directory


def table_counts(session: Session) -> dict[str, int]:
    """Count every domain table to detect partial imports as well as duplicates."""
    return {
        name: session.scalar(select(func.count()).select_from(table)) or 0
        for name, table in Base.metadata.tables.items()
    }


def copy_export(source: Path, target: Path) -> Path:
    """Create a private editable export for corruption and isolation checks."""
    for path in source.iterdir():
        (target / path.name).write_bytes(path.read_bytes())
    return target


def test_dataset_loads_and_passes_quality_checks(
    db_session: Session, dataset_directory: Path
) -> None:
    """A generated export respects migrated constraints and business invariants."""
    counts = load_dataset(db_session, dataset_directory)
    db_session.flush()

    assert counts == table_counts(db_session)
    assert counts["customers"] == 640
    assert counts["products"] == 64
    assert counts["orders"] == 1_000
    assert all(counts.values())
    report = check_quality(db_session)
    assert report.passed, report.as_dict()
    assert all(check.violations == 0 for check in report.checks)


def test_load_does_not_commit(db_session: Session, dataset_directory: Path) -> None:
    """The caller can still undo the complete import with a transaction rollback."""
    load_dataset(db_session, dataset_directory)
    assert table_counts(db_session)["orders"] == 1_000

    db_session.rollback()

    assert not any(table_counts(db_session).values())


def test_repeated_load_refuses_and_preserves_existing_rows(
    db_session: Session, dataset_directory: Path
) -> None:
    """Running the loader twice neither duplicates rows nor removes the first load."""
    load_dataset(db_session, dataset_directory)
    before = table_counts(db_session)

    with pytest.raises(ValueError):
        load_dataset(db_session, dataset_directory)

    assert table_counts(db_session) == before
    assert check_quality(db_session).passed


def test_nonempty_product_table_alone_prevents_load(
    db_session: Session, dataset_directory: Path
) -> None:
    """The empty-database guard checks more than the customer table."""
    db_session.add(
        Product(
            sku="KEEP-001",
            name="Existing product",
            category="Test",
            cost=Decimal("0.00"),
        )
    )
    db_session.flush()
    before = table_counts(db_session)

    with pytest.raises(ValueError):
        load_dataset(db_session, dataset_directory)

    assert table_counts(db_session) == before
    assert db_session.scalar(select(Product.sku)) == "KEEP-001"


def test_tampered_export_is_rejected_before_insertion(
    db_session: Session,
    tmp_path: Path,
    dataset_directory: Path,
) -> None:
    """A hash mismatch cannot leave any partially loaded data behind."""
    copy_export(dataset_directory, tmp_path)
    target = tmp_path / "customers.csv"
    target.write_bytes(target.read_bytes() + b"\n")

    with pytest.raises(ValueError):
        load_dataset(db_session, tmp_path)

    assert not any(table_counts(db_session).values())


def test_ground_truth_is_not_required_for_loading(
    db_session: Session, tmp_path: Path, dataset_directory: Path
) -> None:
    """Evaluation labels remain isolated from the imported business database."""
    directory = copy_export(dataset_directory, tmp_path)
    (directory / "ground_truth.json").unlink()

    counts = load_dataset(db_session, directory)

    assert counts == table_counts(db_session)
    assert counts["orders"] == 1_000
    assert check_quality(db_session).passed


def test_quality_failure_rolls_back_every_insert(
    db_session: Session, tmp_path: Path, dataset_directory: Path
) -> None:
    """Valid hashes cannot bypass business validation or leave partial imports."""
    directory = copy_export(dataset_directory, tmp_path)
    refunds_path = directory / "refunds.csv"
    with refunds_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fields = reader.fieldnames
        assert fields is not None
        refunds = list(reader)
    assert refunds
    # Valid NUMERIC(12, 2), but greater than the refunded line's total.
    refunds[0]["amount"] = "9999999999.99"
    with refunds_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(refunds)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["refunds.csv"]["sha256"] = hashlib.sha256(
        refunds_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="quality"):
        load_dataset(db_session, directory)

    assert not any(table_counts(db_session).values())
    # The enclosing caller transaction remains usable after catching the error.
    db_session.add(
        Product(
            sku="AFTER-FAILURE",
            name="Product after rejected import",
            category="Test",
            cost=Decimal("1.00"),
        )
    )
    db_session.flush()
    assert table_counts(db_session)["products"] == 1


def test_explicit_imported_ids_do_not_break_later_inserts(
    db_session: Session, dataset_directory: Path
) -> None:
    """The loader advances generated ID sequences beyond imported primary keys."""
    load_dataset(db_session, dataset_directory)
    product = Product(
        sku="AFTER-IMPORT",
        name="Product created after import",
        category="Test",
        cost=Decimal("1.00"),
    )
    db_session.add(product)
    db_session.flush()

    assert product.id == 65
    assert table_counts(db_session)["products"] == 65
