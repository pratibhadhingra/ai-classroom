"""Enrolment, placing orders, settling them, and reading a portfolio back.

No FastAPI in this file. It takes a database session and plain values, and
returns plain values, so the rules can be tested without starting a web server.

The three rules that shape all of it:

1. Money is never created or destroyed. A student's cash, the money held against
   their pending orders, and the market value of their holdings always add up.
2. Money is reserved when an order is PLACED, not when it settles. Otherwise a
   student could place five orders for the same rupees.
3. A student's row is locked while their money is being read and written, so two
   simultaneous requests cannot both see the old balance.

Creating a classroom, the teacher's dashboard, and end-of-day settlement across
a whole class live in `features/classes/service.py` -- that module imports
`settle_order` and `get_portfolio` from here rather than duplicating them, so
there is exactly one place that fills an order and exactly one place that adds
up what a student has.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from ...core.money import pct_change, proceeds_for_units, to_money, to_units, units_for_amount
from ...models import ROLE_STUDENT, Account, Classroom, Fund, Holding, Order, Student

ZERO = Decimal("0")


class TradingError(Exception):
    """Something the student did wrong, with a message they can read."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enrolment
# ---------------------------------------------------------------------------


def join_classroom(db: Session, account: Account, join_code: str) -> Student:
    """Enrol a signed-in account in a class, or return their existing enrolment.

    Re-entering the code is not an error and must not reset anyone's portfolio --
    a student who types it again after closing their browser expects to find
    their money where they left it.
    """
    if account.role != ROLE_STUDENT:
        raise TradingError("Teacher accounts run classes rather than joining them")

    classroom = (
        db.query(Classroom)
        .filter(Classroom.join_code == join_code.strip().upper())
        .first()
    )
    if classroom is None:
        raise TradingError("No class with that code. Check the code on the board.")

    existing = (
        db.query(Student)
        .filter(Student.account_id == account.id, Student.classroom_id == classroom.id)
        .first()
    )
    if existing is not None:
        return existing

    student = Student(
        account_id=account.id,
        classroom_id=classroom.id,
        cash=classroom.starting_corpus,
    )
    db.add(student)
    db.commit()
    return student


def enrolment_for(db: Session, account: Account) -> Student | None:
    """The class this student account is currently in, if any."""
    return (
        db.query(Student)
        .filter(Student.account_id == account.id)
        .order_by(Student.joined_at.desc())
        .first()
    )


def classroom_of(db: Session, student: Student) -> Classroom:
    return db.get(Classroom, student.classroom_id)


# ---------------------------------------------------------------------------
# Placing orders
# ---------------------------------------------------------------------------


def place_order(
    db: Session,
    student_id: int,
    scheme_code: int,
    side: str,
    amount: Decimal | None = None,
    units: Decimal | None = None,
) -> Order:
    """Place a buy or sell. It does NOT execute -- it waits for end of day.

    The money moves out of the student's reach immediately even though the order
    has not filled. If it did not, a student with Rs 50,000 could place five
    orders of Rs 50,000 each before any of them settled.
    """
    if side not in ("buy", "sell"):
        raise TradingError("An order is either a buy or a sell")

    fund = db.get(Fund, scheme_code)
    if fund is None:
        raise TradingError("We do not have that fund")

    # with_for_update() locks THIS student's row until the transaction ends. A
    # second request for the same student waits here, then reads the balance
    # this one leaves behind, instead of both reading the old number and both
    # deciding there is enough money. Other students are unaffected -- the lock
    # is on one row, not the table.
    student = (
        db.query(Student).filter(Student.id == student_id).with_for_update().one_or_none()
    )
    if student is None:
        raise TradingError("We could not find you")

    if side == "buy":
        if amount is None or amount <= 0:
            raise TradingError("Type how much you want to invest")
        amount = to_money(amount)
        if amount > student.cash:
            raise TradingError(
                f"You only have Rs {student.cash} to spend, and that includes nothing "
                "already promised to a waiting order."
            )
        student.cash = to_money(student.cash - amount)
        order = Order(
            student_id=student.id,
            scheme_code=scheme_code,
            side="buy",
            status="pending",
            amount=amount,
        )
    else:
        if units is None or units <= 0:
            raise TradingError("Type how many units you want to sell")
        units = to_units(units)

        holding = (
            db.query(Holding)
            .filter(Holding.student_id == student.id, Holding.scheme_code == scheme_code)
            .with_for_update()
            .one_or_none()
        )
        if holding is None or holding.units <= 0:
            raise TradingError("You do not own any of that fund")

        available = holding.units - holding.units_reserved
        if units > available:
            raise TradingError(
                f"You can sell {available} units. The rest are promised to an order "
                "that has not filled yet."
            )

        # Reserved, not removed: the student still owns these units and they are
        # still worth something until the sell actually settles.
        holding.units_reserved = to_units(holding.units_reserved + units)
        order = Order(
            student_id=student.id,
            scheme_code=scheme_code,
            side="sell",
            status="pending",
            units=units,
        )

    db.add(order)
    db.commit()
    return order


def _get_or_create_holding(db: Session, student_id: int, scheme_code: int) -> Holding:
    # No row lock of its own -- safe only because every caller already holds
    # the student row lock for the whole transaction before reaching here.
    holding = (
        db.query(Holding)
        .filter(Holding.student_id == student_id, Holding.scheme_code == scheme_code)
        .one_or_none()
    )
    if holding is None:
        holding = Holding(
            student_id=student_id,
            scheme_code=scheme_code,
            units=ZERO,
            units_reserved=ZERO,
            invested=ZERO,
        )
        db.add(holding)
        db.flush()
    return holding


def settle_order(db: Session, order: Order, student: Student, fund: Fund) -> None:
    """Fill one pending order at the fund's CURRENT price.

    This is the moment the student finds out what they actually paid. The price
    here is the one AMFI published tonight, not the one on screen when they
    clicked.
    """
    # A no-op on anything but a pending order. The caller is expected to have
    # already checked this under the student's row lock, but settling twice
    # would double the units and cash for one payment, so it is checked here too.
    if order.status != "pending":
        return

    nav = fund.nav
    if nav is None or nav <= 0:
        # No usable price. Give the money or units back rather than leaving them
        # stranded, and say why on the order.
        if order.side == "buy":
            student.cash = to_money(student.cash + order.amount)
        else:
            holding = _get_or_create_holding(db, student.id, order.scheme_code)
            holding.units_reserved = to_units(holding.units_reserved - order.units)
        order.status = "rejected"
        order.note = "That fund had no published price, so your order was cancelled."
        order.settled_at = _now()
        return

    holding = _get_or_create_holding(db, student.id, order.scheme_code)

    if order.side == "buy":
        units, cost = units_for_amount(order.amount, nav)
        # The student authorised `amount` but only `cost` could be turned into
        # whole 4dp units. The difference goes back to cash -- it is not ours to
        # keep and it must not vanish.
        remainder = to_money(order.amount - cost)
        student.cash = to_money(student.cash + remainder)

        holding.units = to_units(holding.units + units)
        holding.invested = to_money(holding.invested + cost)

        order.settled_units = units
        order.settled_amount = cost
    else:
        units = order.units
        proceeds = proceeds_for_units(units, nav)

        # Take out the share of what they originally paid that belongs to the
        # units being sold, so the profit shown on what is left stays honest.
        # Sell half your units and half your original investment goes with them.
        if holding.units > 0:
            invested_out = to_money(holding.invested * (units / holding.units))
        else:
            invested_out = ZERO

        holding.units = to_units(holding.units - units)
        holding.units_reserved = to_units(holding.units_reserved - units)
        holding.invested = to_money(holding.invested - invested_out)
        # Guard against a rounding crumb leaving a holding at 0 units but a
        # non-zero cost basis, which would show a phantom profit forever.
        if holding.units <= 0:
            holding.units = ZERO
            holding.invested = ZERO

        student.cash = to_money(student.cash + proceeds)

        order.settled_units = units
        order.settled_amount = proceeds

    order.status = "completed"
    order.settled_nav = nav
    order.settled_nav_date = fund.nav_date
    order.settled_at = _now()


# ---------------------------------------------------------------------------
# Reading a portfolio
# ---------------------------------------------------------------------------


def _reserved_cash(db: Session, student_id: int) -> Decimal:
    """Money already taken out of cash by buy orders that have not filled."""
    total = ZERO
    orders = (
        db.query(Order)
        .filter(
            Order.student_id == student_id,
            Order.status == "pending",
            Order.side == "buy",
        )
        .all()
    )
    for order in orders:
        total += order.amount
    return to_money(total)


def get_portfolio(db: Session, student: Student) -> dict:
    """Everything one student's screen needs, already calculated and rounded.

    All the arithmetic happens here, in Decimal. The browser only ever prints
    these numbers -- doing maths on money in JavaScript would reintroduce exactly
    the float errors Decimal exists to prevent.
    """
    classroom = db.get(Classroom, student.classroom_id)

    rows = (
        db.query(Holding, Fund)
        .join(Fund, Holding.scheme_code == Fund.scheme_code)
        .filter(Holding.student_id == student.id, Holding.units > 0)
        .all()
    )

    holdings = []
    holdings_value = ZERO
    invested_total = ZERO
    newest_nav_date: date | None = None

    for holding, fund in rows:
        value = to_money(holding.units * fund.nav)
        pnl = to_money(value - holding.invested)
        holdings_value += value
        invested_total += holding.invested
        if newest_nav_date is None or fund.nav_date > newest_nav_date:
            newest_nav_date = fund.nav_date

        holdings.append(
            {
                "scheme_code": fund.scheme_code,
                "name": fund.name,
                "risk_band": fund.risk_band,
                "units": holding.units,
                "units_reserved": holding.units_reserved,
                "nav": fund.nav,
                "nav_date": fund.nav_date,
                "value": value,
                "invested": holding.invested,
                "pnl": pnl,
                "pnl_pct": pct_change(pnl, holding.invested),
            }
        )

    holdings.sort(key=lambda h: h["value"], reverse=True)

    pending_rows = (
        db.query(Order, Fund)
        .join(Fund, Order.scheme_code == Fund.scheme_code)
        .filter(Order.student_id == student.id, Order.status == "pending")
        .order_by(Order.placed_at)
        .all()
    )
    pending = [
        {
            "order_id": order.id,
            "side": order.side,
            "scheme_code": fund.scheme_code,
            "name": fund.name,
            "amount": order.amount,
            "units": order.units,
            "placed_at": order.placed_at,
        }
        for order, fund in pending_rows
    ]

    reserved = _reserved_cash(db, student.id)
    holdings_value = to_money(holdings_value)
    total_value = to_money(student.cash + reserved + holdings_value)
    pnl = to_money(total_value - classroom.starting_corpus)

    return {
        "student_id": student.id,
        "name": student.account.name,
        "classroom_name": classroom.name,
        "cash": student.cash,
        "reserved": reserved,
        "holdings_value": holdings_value,
        "total_value": total_value,
        "invested": to_money(invested_total),
        "starting_corpus": classroom.starting_corpus,
        "pnl": pnl,
        "pnl_pct": pct_change(pnl, classroom.starting_corpus),
        "nav_date": newest_nav_date,
        "holdings": holdings,
        "pending": pending,
    }


def get_order_history(db: Session, student: Student) -> list[dict]:
    rows = (
        db.query(Order, Fund)
        .join(Fund, Order.scheme_code == Fund.scheme_code)
        .filter(Order.student_id == student.id)
        .order_by(Order.placed_at.desc())
        .all()
    )
    return [
        {
            "order_id": order.id,
            "side": order.side,
            "scheme_code": fund.scheme_code,
            "name": fund.name,
            "amount": order.amount,
            "units": order.units,
            "status": order.status,
            "placed_at": order.placed_at,
            "settled_nav": order.settled_nav,
            "settled_units": order.settled_units,
            "settled_amount": order.settled_amount,
            "settled_nav_date": order.settled_nav_date,
            "note": order.note,
        }
        for order, fund in rows
    ]
