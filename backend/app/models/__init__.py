"""The six tables, one file per class.

account   -- who someone is: name, email, password, current session
classroom -- one per class a teacher creates
student   -- an account's enrolment in a classroom, and their money
fund      -- the twelve funds students can buy, with the latest price
holding   -- how many units a student owns of a fund
orders    -- every buy and sell ever placed, pending or settled

Every money column is NUMERIC, which Postgres stores and arithmetics exactly and
psycopg hands back as a Python Decimal. Nothing here touches a float.

This package re-exports every model class and the ROLE_* constants, so
`from app.models import Account, Classroom, Student, Fund, Holding, Order` keeps
working exactly as it did when these all lived in one models.py -- no call site
outside this package needs to know the tables live in separate files.

The classes reference each other through string-based relationships (e.g.
`Mapped["Classroom"]` inside student.py) rather than importing one another's
module directly. SQLAlchemy resolves those strings against the shared
declarative registry (Base, from core/database.py) once every class has been
defined -- which importing all six modules right here guarantees -- so there is
no import-order circularity between, say, Student and Classroom even though
each refers to the other.
"""

from __future__ import annotations

from .common import ROLE_STUDENT, ROLE_TEACHER
from .account import Account
from .classroom import Classroom
from .student import Student
from .fund import Fund
from .holding import Holding
from .order import Order

__all__ = [
    "ROLE_STUDENT",
    "ROLE_TEACHER",
    "Account",
    "Classroom",
    "Student",
    "Fund",
    "Holding",
    "Order",
]
