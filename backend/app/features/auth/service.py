"""Signing up, signing in, and knowing who is making a request.

Deliberately small. There is no email verification, no password reset and no
refresh-token dance, because none of them can be done honestly without an email
provider. What is here is the part that has to be right: passwords are never
stored or logged, and a session can be revoked.
"""

from __future__ import annotations

import re
import secrets

import bcrypt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models import ROLE_STUDENT, ROLE_TEACHER, Account

MIN_PASSWORD_LENGTH = 8

# Deliberately loose. Strict email regexes reject valid addresses and still let
# typos through; the only real test of an address is sending mail to it, which
# this project does not do.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Something the user can fix, with a message they can read."""


def hash_password(password: str) -> str:
    """bcrypt, with a fresh random salt generated inside the hash.

    bcrypt is deliberately slow, which is the point: it makes guessing passwords
    in bulk expensive. The salt means two people choosing the same password get
    two different hashes, so a match tells an attacker nothing.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    # checkpw re-hashes the candidate with the salt stored in the hash and
    # compares in constant time, so the comparison itself leaks nothing.
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# Computed once, at import time, so an unknown email still pays the same bcrypt
# cost as a known one. Without this, checkpw is skipped entirely when
# `account is None`, and the missing delay tells an attacker the email does not
# exist -- the same information the shared error message is meant to hide.
_DUMMY_HASH = hash_password("not-a-real-password")


def new_session_token() -> str:
    """A long random string. secrets, not random: this is a credential."""
    return secrets.token_urlsafe(32)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def sign_up(db: Session, role: str, name: str, email: str, password: str) -> Account:
    if role not in (ROLE_TEACHER, ROLE_STUDENT):
        raise AuthError("Choose whether you are a teacher or a student")

    name = name.strip()
    if not name:
        raise AuthError("Type your name")

    email = normalise_email(email)
    if not EMAIL_RE.match(email):
        raise AuthError("That does not look like an email address")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Use at least {MIN_PASSWORD_LENGTH} characters for your password")

    if db.query(Account).filter(Account.email == email).first() is not None:
        raise AuthError("There is already an account with that email. Sign in instead.")

    account = Account(
        role=role,
        name=name,
        email=email,
        password_hash=hash_password(password),
        session_token=new_session_token(),
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        # The pre-check above raced with another signup for the same email
        # between the SELECT and this INSERT. Same clean error either way.
        db.rollback()
        raise AuthError("There is already an account with that email. Sign in instead.")
    return account


def sign_in(db: Session, email: str, password: str) -> Account:
    account = db.query(Account).filter(Account.email == normalise_email(email)).first()

    # Always run the bcrypt comparison, even against a dummy hash when there is
    # no account, so the two cases take the same time as well as giving the
    # same message -- otherwise the response time would tell them apart.
    password_hash = account.password_hash if account is not None else _DUMMY_HASH
    password_ok = verify_password(password, password_hash)

    # One message for "no such email" and "wrong password". Telling them apart
    # would let someone check which addresses have accounts here.
    if account is None or not password_ok:
        raise AuthError("That email and password do not match")

    # A fresh token per sign-in, so an old one stops working.
    account.session_token = new_session_token()
    db.commit()
    return account


def sign_out(db: Session, account: Account) -> None:
    account.session_token = None
    db.commit()


def account_for_token(db: Session, token: str | None) -> Account | None:
    if not token:
        return None
    return db.query(Account).filter(Account.session_token == token).first()
