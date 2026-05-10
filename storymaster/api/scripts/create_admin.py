"""Create or update a Storymaster user with a password.

Usage:
    storymaster-create-admin --username alice
    storymaster-create-admin --username alice --password s3cret  # non-interactive

Targets STORYMASTER_DB_URL / STORYMASTER_DB_PATH the same way the API server
does. If the user already exists, the password is updated; otherwise a new
user row is created.
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from storymaster.api.security import hash_password
from storymaster.model.database.schema.base import User
from storymaster.sync_server.database import SessionLocal


def _prompt_password() -> str:
    while True:
        pw = getpass.getpass("Password: ")
        if not pw:
            print("Password may not be empty.", file=sys.stderr)
            continue
        confirm = getpass.getpass("Confirm: ")
        if pw != confirm:
            print("Passwords do not match. Try again.", file=sys.stderr)
            continue
        return pw


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset a Storymaster user.")
    parser.add_argument("--username", required=True, help="Username to create or update.")
    parser.add_argument(
        "--password",
        help="Password (omit to be prompted; --password is mostly for scripted setups).",
    )
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Mark the user inactive (lockout). Default is active.",
    )
    args = parser.parse_args()

    password = args.password or _prompt_password()
    pw_hash = hash_password(password)

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.username == args.username)).scalar_one_or_none()
        if user is None:
            user = User(username=args.username, password_hash=pw_hash, is_active=not args.inactive)
            db.add(user)
            action = "created"
        else:
            user.password_hash = pw_hash
            user.is_active = not args.inactive
            action = "updated"
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    print(f"User {args.username!r} {action} (id={user.id}, active={user.is_active}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
