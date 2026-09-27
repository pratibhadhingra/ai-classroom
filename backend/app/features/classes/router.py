"""Teacher endpoints: creating classes, the dashboard, and running end of day.

Every route here checks that the signed-in teacher owns the class in the path.
Without that, changing the id in the URL would open somebody else's dashboard.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.dependencies import require_teacher
from ...core.schemas import as_decimal, json_safe
from ...models import Account
from . import service
from .schemas import CreateClassRequest
from .service import TradingError

router = APIRouter(prefix="/api/classes", tags=["classes"])


def _summary(classroom) -> dict:
    return {
        "classroom_id": classroom.id,
        "name": classroom.name,
        # Public: this is the code that goes on the whiteboard. It only lets
        # someone join. Everything that changes a class needs the teacher's
        # signed-in account, not this.
        "join_code": classroom.join_code,
        "starting_corpus": classroom.starting_corpus,
        "created_at": classroom.created_at,
    }


@router.post("")
def create_class(
    body: CreateClassRequest,
    teacher: Account = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    try:
        corpus = as_decimal(body.starting_corpus, "The starting money")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    try:
        classroom = service.create_classroom(db, teacher, body.name, corpus)
    except TradingError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return json_safe(_summary(classroom))


@router.get("")
def my_classes(teacher: Account = Depends(require_teacher), db: Session = Depends(get_db)):
    return json_safe([_summary(c) for c in service.classrooms_of(db, teacher)])


@router.get("/{classroom_id}/dashboard")
def dashboard(
    classroom_id: int,
    teacher: Account = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    try:
        classroom = service.classroom_for_teacher(db, teacher, classroom_id)
    except TradingError as error:
        raise HTTPException(status_code=404, detail=str(error))
    return json_safe(service.get_dashboard(db, classroom))


@router.post("/{classroom_id}/end-of-day")
def end_of_day(
    classroom_id: int,
    teacher: Account = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Fetch tonight's real prices, then fill every waiting order at them.

    This stands in for the 11pm NAV publication. Only the teacher can trigger it:
    a student able to close the day at will would be choosing their own price.
    """
    try:
        classroom = service.classroom_for_teacher(db, teacher, classroom_id)
    except TradingError as error:
        raise HTTPException(status_code=404, detail=str(error))

    try:
        result = service.run_end_of_day(db, classroom.id)
    except RuntimeError as error:
        # connectors/amfi.py raises this when the download comes back empty. We
        # keep the prices already stored rather than wiping them, and say so.
        raise HTTPException(status_code=503, detail=f"Could not reach AMFI: {error}")

    return json_safe(result)
