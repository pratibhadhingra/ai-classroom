"""Student endpoints: join a class, view portfolio, place and list orders.

Everything here is scoped to whoever is signed in. There is no student id in any
path: the identity comes from the session token, so there is no number in a URL
for someone to change in order to look at a classmate's money.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.dependencies import require_student
from ...core.schemas import as_decimal, json_safe
from ...models import Account
from . import service as trading
from .schemas import JoinRequest, OrderRequest
from .service import TradingError

router = APIRouter(prefix="/api", tags=["students"])


def _enrolment_or_400(db: Session, account: Account):
    student = trading.enrolment_for(db, account)
    if student is None:
        raise HTTPException(
            status_code=400,
            detail="You have not joined a class yet. Ask your teacher for the code.",
        )
    return student


@router.post("/join")
def join(
    body: JoinRequest,
    account: Account = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        student = trading.join_classroom(db, account, body.join_code)
    except TradingError as error:
        raise HTTPException(status_code=400, detail=str(error))

    classroom = trading.classroom_of(db, student)
    return json_safe(
        {
            "student_id": student.id,
            "classroom_id": classroom.id,
            "classroom_name": classroom.name,
            "join_code": classroom.join_code,
            "cash": student.cash,
        }
    )


@router.get("/me/portfolio")
def portfolio(account: Account = Depends(require_student), db: Session = Depends(get_db)):
    student = _enrolment_or_400(db, account)
    return json_safe(trading.get_portfolio(db, student))


@router.get("/me/orders")
def order_history(account: Account = Depends(require_student), db: Session = Depends(get_db)):
    student = _enrolment_or_400(db, account)
    return json_safe(trading.get_order_history(db, student))


@router.post("/me/orders")
def place_order(
    body: OrderRequest,
    account: Account = Depends(require_student),
    db: Session = Depends(get_db),
):
    student = _enrolment_or_400(db, account)

    try:
        amount = as_decimal(body.amount, "The amount")
        units = as_decimal(body.units, "The number of units")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    try:
        order = trading.place_order(
            db,
            student_id=student.id,
            scheme_code=body.scheme_code,
            side=body.side,
            amount=amount,
            units=units,
        )
    except TradingError as error:
        # 400, not 500: running out of money is a normal thing for a student to
        # do, not a bug in the server.
        raise HTTPException(status_code=400, detail=str(error))

    return json_safe(
        {
            "order_id": order.id,
            "side": order.side,
            "scheme_code": order.scheme_code,
            "amount": order.amount,
            "units": order.units,
            "status": order.status,
            "placed_at": order.placed_at,
        }
    )
