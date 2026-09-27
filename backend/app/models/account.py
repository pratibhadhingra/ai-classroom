"""account -- who someone is: name, email, password, current session.

Identity and enrolment are separate on purpose. An account is a person; a
student row (see student.py) is that person taking part in one class. Keeping
them apart means a display name never has to be unique -- two students called
Rahul are two accounts with two different email addresses, and nothing
collides.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .common import _now


class Account(Base):
    """A person who can sign in. Teacher or student."""

    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(10), index=True)  # teacher | student
    name: Mapped[str] = mapped_column(String(60))

    # Stored lowercased and stripped, so Rohan@x.com and rohan@x.com are one
    # account rather than two.
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)

    # A bcrypt hash, never the password. bcrypt carries its own random salt
    # inside the hash, so two people with the same password get different rows
    # and neither can be recognised from the other.
    password_hash: Mapped[str] = mapped_column(String(120))

    # The current session. A long random string handed to the browser at login
    # and sent back on every request. Nulling it signs the account out
    # everywhere, which a stateless token could not do.
    session_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
