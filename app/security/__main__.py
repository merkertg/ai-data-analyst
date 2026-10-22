"""Manage API tokens from the server's terminal: issue, list and revoke.

    uv run python -m app.security issue --name "Anna" --role analyst --days 90
    uv run python -m app.security list
    uv run python -m app.security revoke <token-id>

Token management needs direct database access (DATABASE_URL); there is no
HTTP endpoint for it, so a leaked API token cannot create new tokens.
"""

import argparse
import sys
import uuid
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import DatabaseNotConfigured, get_engine
from app.security.service import issue_token, list_tokens, revoke_token
from app.security.tokens import Role


def _parser() -> argparse.ArgumentParser:
    """Three sub-commands with explicit, validated arguments."""
    parser = argparse.ArgumentParser(prog="python -m app.security", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    issue = commands.add_parser("issue", help="create a token and print it once")
    issue.add_argument("--name", required=True, help="who or what uses the token")
    issue.add_argument("--role", required=True, choices=[role.value for role in Role])
    issue.add_argument("--days", type=int, help="expire after this many days")
    commands.add_parser("list", help="show tokens without their secret values")
    revoke = commands.add_parser("revoke", help="stop a token from working")
    revoke.add_argument("token_id", type=uuid.UUID)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command in its own transaction; print a safe error on failure."""
    args = _parser().parse_args(argv)
    try:
        with Session(get_engine()) as session:
            if args.command == "issue":
                row, token = issue_token(session, args.name, Role(args.role), args.days)
                session.commit()
                print(f"id:      {row.id}")
                print(f"role:    {row.role}")
                print(f"expires: {row.expires_at or 'never'}")
                print(f"token:   {token}")
                print("Store the token now: it cannot be shown again.")
            elif args.command == "list":
                for row in list_tokens(session):
                    state = "revoked" if row.revoked_at else "active"
                    print(
                        f"{row.id}  {row.prefix}…  {row.role:<7}  {state:<7}  "
                        f"expires {row.expires_at or 'never'}  {row.name}"
                    )
            elif not revoke_token(session, args.token_id):
                print("No active token with this id.", file=sys.stderr)
                return 1
            else:
                session.commit()
                print("Token revoked.")
    except ValueError as error:
        print(f"Invalid value: {error}", file=sys.stderr)
        return 2
    except (DatabaseNotConfigured, SQLAlchemyError):
        print(
            "Database unavailable: check DATABASE_URL and migrations.", file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
