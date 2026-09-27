"""orders -- every buy and sell ever placed, pending or settled."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .common import MONEY, NAV, UNITS, _now


class Order(Base):
    # "order" is a reserved word in SQL (ORDER BY), so the table is "orders".
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), index=True)
    scheme_code: Mapped[int] = mapped_column(ForeignKey("fund.scheme_code"), index=True)

    side: Mapped[str] = mapped_column(String(4))  # "buy" or "sell"
    status: Mapped[str] = mapped_column(String(10), index=True)  # pending/completed/rejected

    # A buy is placed in rupees ("put Rs 10,000 in"); a sell is placed in units
    # ("sell 200 of my units"). Only one of these is set on any given row.
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    units: Mapped[Decimal | None] = mapped_column(UNITS, nullable=True)

    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Filled in at end of day. Keeping the NAV the order actually settled at --
    # not just today's NAV -- is what makes this table a real audit trail: every
    # rupee that moved can be traced back to a row and the price it moved at.
    settled_nav: Mapped[Decimal | None] = mapped_column(NAV, nullable=True)
    settled_units: Mapped[Decimal | None] = mapped_column(UNITS, nullable=True)
    settled_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    settled_nav_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Why a rejected order was rejected, in words the student can read.
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Resolved by name against the shared Base registry -- see classroom.py.
    student: Mapped["Student"] = relationship(back_populates="orders")  # noqa: F821
    fund: Mapped["Fund"] = relationship()  # noqa: F821
