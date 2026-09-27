"""Sign up, sign in, sign out, and "who am I"."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.dependencies import current_account
from ...core.schemas import json_safe
from ...models import ROLE_STUDENT, Account
from ..trading import service as trading
from . import service as auth
from .schemas import SignInRequest, SignUpRequest
from .service import AuthError

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session(account: Account) -> dict:
    """What the browser is told after signing in.

    Note what is absent: the password hash never leaves the database, and no
    endpoint returns it in any form.
    """
    return {
        "token": account.session_token,
        "account": {
            "id": account.id,
            "role": account.role,
            "name": account.name,
            "email": account.email,
        },
    }


@router.post("/signup")
def signup(body: SignUpRequest, db: Session = Depends(get_db)):
    try:
        account = auth.sign_up(db, body.role, body.name, body.email, body.password)
    except AuthError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return json_safe(_session(account))


@router.post("/login")
def login(body: SignInRequest, db: Session = Depends(get_db)):
    try:
        account = auth.sign_in(db, body.email, body.password)
    except AuthError as error:
        # 401, and the same message whether the email or the password was wrong,
        # so this cannot be used to discover which addresses have accounts.
        raise HTTPException(status_code=401, detail=str(error))
    return json_safe(_session(account))


@router.post("/logout")
def logout(account: Account = Depends(current_account), db: Session = Depends(get_db)):
    auth.sign_out(db, account)
    return {"ok": True}


@router.get("/me")
def me(account: Account = Depends(current_account), db: Session = Depends(get_db)):
    """Used on page load to restore a session without a second round trip.

    For a student it also says which class they are in, so the app knows whether
    to show the join screen or their portfolio.
    """
    payload = {
        "account": {
            "id": account.id,
            "role": account.role,
            "name": account.name,
            "email": account.email,
        },
        "enrolment": None,
    }

    if account.role == ROLE_STUDENT:
        student = trading.enrolment_for(db, account)
        if student is not None:
            classroom = trading.classroom_of(db, student)
            payload["enrolment"] = {
                "student_id": student.id,
                "classroom_id": classroom.id,
                "classroom_name": classroom.name,
                "join_code": classroom.join_code,
            }

    return json_safe(payload)
