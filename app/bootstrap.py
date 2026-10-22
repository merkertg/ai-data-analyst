"""Prepare a fresh stand for the demonstration; safe to run on every start.

    python -m app.bootstrap --token-file /run/ai-data-analyst/ui_token

1. Refuses to continue unless the schema is at the latest migration.
2. Loads the seed 42 demo dataset only when every sales table is empty;
   existing data is never changed (--no-data or DEMO_DATA=false skips it).
3. Keeps a valid analyst token for the Streamlit interface in --token-file.
   A missing, revoked or unknown token is replaced; the token itself is never
   printed.

Docker Compose runs this once after the migrations and before the interface.
"""

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.data.generate import export_dataset, generate_dataset
from app.data.load import load_dataset
from app.db.models import ApiToken, Customer
from app.db.readiness import current_revision, expected_revision
from app.db.session import DatabaseNotConfigured, get_engine
from app.security.service import authenticate, issue_token, revoke_token
from app.security.tokens import Role

DEMO_SEED = 42
UI_TOKEN_NAME = "Streamlit (Docker demo)"


def ensure_demo_data(session: Session) -> dict[str, int] | None:
    """Load the seed 42 bundle into empty tables; None when data exists.

    The loader itself refuses partially filled tables, so a half-loaded
    database fails loudly instead of being topped up.
    """
    if session.scalar(select(Customer.id).limit(1)) is not None:
        return None
    with tempfile.TemporaryDirectory() as directory:
        bundle = Path(directory) / "demo"
        export_dataset(generate_dataset(seed=DEMO_SEED), bundle)
        return load_dataset(session, bundle)


def ensure_ui_token(session: Session, path: Path) -> str:
    """Keep the file's token if it still works, otherwise issue a new one.

    Returns "kept" or "issued". Earlier demo tokens are revoked when a new one
    is issued, so at most one interface token stays active.
    """
    try:
        current = path.read_text(encoding="utf-8").strip()
    except OSError:
        current = ""
    if current and authenticate(session, current) is not None:
        return "kept"
    for row in session.scalars(
        select(ApiToken).where(
            ApiToken.name == UI_TOKEN_NAME, ApiToken.revoked_at.is_(None)
        )
    ):
        revoke_token(session, row.id)
    _, token = issue_token(session, UI_TOKEN_NAME, Role.ANALYST)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a new file readable only by its owner, then swap it in atomically.
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(token + "\n")
    temporary.replace(path)
    return "issued"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the three steps in one transaction and print a JSON summary."""
    parser = argparse.ArgumentParser(
        prog="python -m app.bootstrap", description=__doc__
    )
    parser.add_argument("--token-file", type=Path, help="where the UI token is kept")
    parser.add_argument(
        "--no-data",
        action="store_true",
        default=os.environ.get("DEMO_DATA", "true").strip().lower() == "false",
        help="do not load the demo dataset (also DEMO_DATA=false)",
    )
    args = parser.parse_args(argv)
    try:
        engine = get_engine()
        revision = current_revision(engine)
        if revision != expected_revision():
            print(
                json.dumps({"error": "apply migrations first", "revision": revision}),
                file=sys.stderr,
            )
            return 1
        with Session(engine) as session:
            loaded = None if args.no_data else ensure_demo_data(session)
            token = (
                None
                if args.token_file is None
                else ensure_ui_token(session, args.token_file)
            )
            session.commit()
    except (DatabaseNotConfigured, SQLAlchemyError, ValueError, OSError):
        print(
            json.dumps({"error": "bootstrap failed; check DATABASE_URL and data"}),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "revision": revision,
                "demo_data": "skipped"
                if args.no_data
                else ("loaded" if loaded else "already present"),
                "rows": loaded,
                "ui_token": token,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
