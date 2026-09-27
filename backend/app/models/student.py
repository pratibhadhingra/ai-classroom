"""student -- an account's enrolment in a classroom, and their money."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .common import MONEY, _now


class Student(Base):
    """One account taking part in one classroom, with their money."""

    __tablename__ = "student"
    # An account joins a given class once. Re-entering the code returns the
    # existing enrolment rather than resetting anyone's portfolio.
    __table_args__ = (
        UniqueConstraint("account_id", "classroom_id", name="uq_enrolment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), index=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classroom.id"), index=True)

    # Spendable cash. Money reserved by a pending buy has ALREADY been taken out
    # of here -- see features/trading/service.py. Otherwise the same rupee could
    # back several unfilled orders at once.
    cash: Mapped[Decimal] = mapped_column(MONEY)

    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Resolved by name against the shared Base registry -- see classroom.py.
    account: Mapped["Account"] = relationship()  # noqa: F821
    classroom: Mapped["Classroom"] = relationship(back_populates="students")  # noqa: F821
    holdings: Mapped[list["Holding"]] = relationship(back_populates="student")  # noqa: F821
    orders: Mapped[list["Order"]] = relationship(back_populates="student")  # noqa: F821
