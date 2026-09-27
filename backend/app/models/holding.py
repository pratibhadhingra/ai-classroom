"""holding -- how many units a student owns of a fund."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .common import MONEY, UNITS


class Holding(Base):
    __tablename__ = "holding"
    __table_args__ = (
        UniqueConstraint("student_id", "scheme_code", name="uq_holding_per_fund"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), index=True)
    scheme_code: Mapped[int] = mapped_column(ForeignKey("fund.scheme_code"), index=True)

    units: Mapped[Decimal] = mapped_column(UNITS)

    # Units promised to a pending sell. Still owned and still valued, but not
    # available to sell a second time.
    units_reserved: Mapped[Decimal] = mapped_column(UNITS)

    # Total rupees put into this fund, net of what has been sold back out. This
    # is what lets us show "you put in Rs 20,000, it is worth Rs 20,196" rather
    # than only the current value.
    invested: Mapped[Decimal] = mapped_column(MONEY)

    # Resolved by name against the shared Base registry -- see classroom.py.
    student: Mapped["Student"] = relationship(back_populates="holdings")  # noqa: F821
    fund: Mapped["Fund"] = relationship()  # noqa: F821
