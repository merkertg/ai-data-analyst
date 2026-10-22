"""Compare a verified export with real PostgreSQL values in the isolated test DB."""

from contextlib import nullcontext
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.data.generate import export_dataset, generate_dataset
from app.data.load import load_dataset
from app.db.base import Base
from app.evals.__main__ import check_database_matches


@pytest.fixture(scope="module")
def eval_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small, valid generated bundle with all six domain tables populated."""
    directory = tmp_path_factory.mktemp("eval-identity") / "bundle"
    export_dataset(generate_dataset(seed=42, order_count=1000), directory)
    return directory


@pytest.fixture
def loaded_eval_bundle(
    db_session: Session, eval_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Reuse the test transaction; the checker never sees the development DB."""
    load_dataset(db_session, eval_bundle)

    def sessions(*, read_only: bool) -> nullcontext[Session]:
        """Supply only the explicit *_test session to the evaluation checker."""
        assert read_only is True
        return nullcontext(db_session)

    monkeypatch.setattr("app.evals.__main__.LazySession", sessions)
    return eval_bundle


def test_postgresql_matches_export_despite_timestamp_zone_formatting(
    db_session: Session, loaded_eval_bundle: Path
) -> None:
    """UTC SQL timestamps equal Moscow-offset CSV instants; NUMERIC stays exact."""
    db_session.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    check_database_matches(loaded_eval_bundle)


@pytest.mark.parametrize(
    ("name", "field"),
    [
        ("customers", "name"),
        ("products", "cost"),
        ("orders", "ordered_at"),
        ("order_items", "unit_price"),
        ("refunds", "amount"),
        ("inventory_snapshots", "quantity"),
    ],
)
def test_one_changed_value_is_rejected_without_any_count_change(
    db_session: Session, loaded_eval_bundle: Path, name: str, field: str
) -> None:
    """The guard detects real equal-size mutations, including warehouse rows."""
    table = Base.metadata.tables[name]
    original = (
        db_session.execute(select(table).order_by(table.c.id).limit(1)).mappings().one()
    )
    value = original[field]
    if name == "customers":
        replacement = value + " changed"
    elif name == "orders":
        replacement = value - timedelta(seconds=1)
    elif name == "inventory_snapshots":
        replacement = value + 1
    else:
        replacement = value + Decimal("0.01")
    db_session.execute(
        table.update().where(table.c.id == original["id"]).values({field: replacement})
    )

    with pytest.raises(ValueError, match=f"^{name}: database content differs"):
        check_database_matches(loaded_eval_bundle)


def test_missing_inventory_row_is_rejected(
    db_session: Session, loaded_eval_bundle: Path
) -> None:
    """A shortened inventory stream cannot silently pass the six-table check."""
    stock = Base.metadata.tables["inventory_snapshots"]
    first_id = db_session.scalar(select(stock.c.id).order_by(stock.c.id).limit(1))
    db_session.execute(stock.delete().where(stock.c.id == first_id))
    with pytest.raises(ValueError, match="^inventory_snapshots:"):
        check_database_matches(loaded_eval_bundle)
