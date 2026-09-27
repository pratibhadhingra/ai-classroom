"""classroom -- one per class a teacher creates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .common import MONEY, _now


class Classroom(Base):
    __tablename__ = "classroom"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("account.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))

    # Public: this is what goes on the whiteboard. It only lets someone join.
    # Everything that changes a class needs the teacher's signed-in account.
    join_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)

    starting_corpus: Mapped[Decimal] = mapped_column(MONEY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # "Account" and "Student" are resolved by name against the shared Base
    # registry once every model module has been imported (see
    # models/__init__.py), so this file never has to import theirs directly.
    teacher: Mapped["Account"] = relationship()  # noqa: F821
    students: Mapped[list["Student"]] = relationship(back_populates="classroom")  # noqa: F821
