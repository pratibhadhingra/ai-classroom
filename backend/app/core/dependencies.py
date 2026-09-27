"""Who is making this request.

FastAPI calls these before the endpoint body runs, so an endpoint that declares
`teacher: Account = Depends(require_teacher)` can assume it has one and get on
with the work.
"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from ..models import ROLE_STUDENT, ROLE_TEACHER, Account
from ..features.auth import service as auth


def current_account(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Account:
    """Read the session token from the Authorization header and find its owner.

    The header looks like `Authorization: Bearer <token>`. The token is opaque --
    it carries no information, it is just a long random string that we look up.
    That is deliberate: signing someone out is a matter of clearing one column,
    which a self-contained token could not offer without a blocklist.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    account = auth.account_for_token(db, token)
    if account is None:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    return account


def require_teacher(account: Account = Depends(current_account)) -> Account:
    if account.role != ROLE_TEACHER:
        raise HTTPException(status_code=403, detail="That is only for teacher accounts.")
    return account


def require_student(account: Account = Depends(current_account)) -> Account:
    if account.role != ROLE_STUDENT:
        raise HTTPException(status_code=403, detail="That is only for student accounts.")
    return account
