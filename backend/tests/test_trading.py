"""Tests for the rules that move money.

These run against the real Postgres rather than a mock, because most of what is
being checked IS database behaviour -- row locks, unique constraints, and exact
NUMERIC arithmetic. A mock would only assert our own assumptions back at us.

Each test makes its own classroom with a random name and deletes everything it
created afterwards. The `fund` table is shared, seeded once, and never touched.

Run from backend/:  .venv/Scripts/python.exe -m pytest tests -q
"""

from __future__ import annotations

import secrets
import threading
from decimal import Decimal

import pytest

from app.core.database import SessionLocal
from app.models import Account, Classroom, Holding, Order, Student
from app.features.auth import service as auth
from app.features.classes import service as classes_service
from app.features.trading import service as trading
from app.features.auth.service import AuthError
from app.features.trading.service import TradingError

# A cheap fund and an expensive one, both from the seeded universe.
NIFTY50 = 118482        # BANDHAN Nifty 50 Index Fund, around Rs 52
SMALLCAP = 125354       # Axis Small Cap Fund, around Rs 136

CORPUS = Decimal("100000.00")


def _unique(prefix: str) -> str:
    """Names and emails that cannot collide with a parallel run or a leftover row."""
    return f"{prefix}-{secrets.token_hex(4)}"


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def classroom(db):
    """A teacher with one empty class. Everything it creates is removed after."""
    teacher = auth.sign_up(
        db, "teacher", "Test Teacher", f"{_unique('teacher')}@test.invalid", "password123"
    )
    room = classes_service.create_classroom(db, teacher, _unique("Class"), CORPUS)

    yield room

    student_ids = [
        s.id for s in db.query(Student).filter(Student.classroom_id == room.id).all()
    ]
    account_ids = [
        s.account_id for s in db.query(Student).filter(Student.classroom_id == room.id).all()
    ]
    if student_ids:
        db.query(Order).filter(Order.student_id.in_(student_ids)).delete(
            synchronize_session=False
        )
        db.query(Holding).filter(Holding.student_id.in_(student_ids)).delete(
            synchronize_session=False
        )
    db.query(Student).filter(Student.classroom_id == room.id).delete(
        synchronize_session=False
    )
    db.query(Classroom).filter(Classroom.id == room.id).delete(synchronize_session=False)
    if account_ids:
        db.query(Account).filter(Account.id.in_(account_ids)).delete(
            synchronize_session=False
        )
    db.query(Account).filter(Account.id == teacher.id).delete(synchronize_session=False)
    db.commit()


def _enrol(db, room, label="Student"):
    account = auth.sign_up(
        db, "student", label, f"{_unique('student')}@test.invalid", "password123"
    )
    return trading.join_classroom(db, account, room.join_code)


def _fund(db, scheme_code):
    from app.models import Fund

    return db.get(Fund, scheme_code)


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------


def test_new_student_starts_with_the_class_corpus(db, classroom):
    """Everyone begins on exactly the same amount, to the paisa."""
    student = _enrol(db, classroom)
    assert student.cash == CORPUS


def test_placing_a_buy_reserves_the_cash_immediately(db, classroom):
    """The money leaves cash when the order is PLACED, not when it settles.

    If it did not, a student could place several orders against the same rupees
    before any of them filled.
    """
    student = _enrol(db, classroom)
    trading.place_order(db, student.id, NIFTY50, "buy", amount=Decimal("30000"))
    db.refresh(student)

    assert student.cash == Decimal("70000.00")

    portfolio = trading.get_portfolio(db, student)
    assert portfolio["reserved"] == Decimal("30000.00")
    # Reserved money is still the student's -- it has moved pocket, not vanished.
    assert portfolio["total_value"] == CORPUS


def test_a_second_order_cannot_spend_reserved_cash(db, classroom):
    """Two orders of 60,000 against 100,000: the second must be refused."""
    student = _enrol(db, classroom)
    trading.place_order(db, student.id, NIFTY50, "buy", amount=Decimal("60000"))

    with pytest.raises(TradingError):
        trading.place_order(db, student.id, SMALLCAP, "buy", amount=Decimal("60000"))


def test_buying_more_than_you_have_is_refused(db, classroom):
    student = _enrol(db, classroom)
    with pytest.raises(TradingError):
        trading.place_order(db, student.id, NIFTY50, "buy", amount=Decimal("100000.01"))


def test_selling_units_you_do_not_own_is_refused(db, classroom):
    student = _enrol(db, classroom)
    with pytest.raises(TradingError):
        trading.place_order(db, student.id, NIFTY50, "sell", units=Decimal("10"))


def test_settling_a_buy_conserves_every_paisa(db, classroom):
    """The core guarantee: money is moved, never created or destroyed.

    Units are rounded DOWN, so the cost of those units is usually a fraction less
    than the amount authorised. That remainder must come back to cash.
    """
    student = _enrol(db, classroom)
    order = trading.place_order(db, student.id, SMALLCAP, "buy", amount=Decimal("15000"))

    fund = _fund(db, SMALLCAP)
    trading.settle_order(db, order, student, fund)
    db.commit()

    holding = (
        db.query(Holding)
        .filter(Holding.student_id == student.id, Holding.scheme_code == SMALLCAP)
        .one()
    )

    # Units were rounded down, so they cost no more than was authorised.
    assert order.settled_amount <= Decimal("15000.00")
    # Whatever could not be turned into units is back in cash.
    assert student.cash == Decimal("85000.00") + (
        Decimal("15000.00") - order.settled_amount
    )
    # And the whole portfolio still adds up to what they started with.
    portfolio = trading.get_portfolio(db, student)
    assert portfolio["cash"] + portfolio["holdings_value"] == CORPUS
    assert holding.invested == order.settled_amount


def test_units_are_rounded_down_never_up(db, classroom):
    """Rounding up would allot units the fund never issued -- inventing money."""
    student = _enrol(db, classroom)
    order = trading.place_order(db, student.id, SMALLCAP, "buy", amount=Decimal("15000"))

    fund = _fund(db, SMALLCAP)
    trading.settle_order(db, order, student, fund)
    db.commit()

    # units * nav must never exceed what the student actually authorised
    assert order.settled_units * fund.nav <= Decimal("15000.00")


def test_an_order_settles_at_the_price_when_it_fills(db, classroom):
    """Not the price shown when it was placed. This is the whole trading model.

    The fund's NAV is moved between placing and settling to prove the settled
    price follows the fund, not a figure captured at order time.
    """
    student = _enrol(db, classroom)
    fund = _fund(db, NIFTY50)
    price_when_ordered = fund.nav

    order = trading.place_order(db, student.id, NIFTY50, "buy", amount=Decimal("10000"))

    new_price = (price_when_ordered * Decimal("1.10")).quantize(Decimal("0.000001"))
    fund.nav = new_price
    db.commit()

    trading.settle_order(db, order, student, fund)
    db.commit()

    assert order.settled_nav == new_price
    assert order.settled_nav != price_when_ordered
    # A higher price buys fewer units, which is the lesson the app teaches.
    assert order.settled_units < Decimal("10000") / price_when_ordered


def test_selling_returns_cash_and_reduces_the_cost_basis(db, classroom):
    """Sell half the units and half the original investment goes with them.

    Otherwise the profit shown on what is left would be wrong.
    """
    student = _enrol(db, classroom)
    fund = _fund(db, NIFTY50)

    buy = trading.place_order(db, student.id, NIFTY50, "buy", amount=Decimal("20000"))
    trading.settle_order(db, buy, student, fund)
    db.commit()

    holding = (
        db.query(Holding)
        .filter(Holding.student_id == student.id, Holding.scheme_code == NIFTY50)
        .one()
    )
    invested_before = holding.invested
    half = (holding.units / 2).quantize(Decimal("0.0001"))

    sell = trading.place_order(db, student.id, NIFTY50, "sell", units=half)
    db.refresh(holding)
    assert holding.units_reserved == half  # locked, so it cannot be sold twice

    trading.settle_order(db, sell, student, fund)
    db.commit()
    db.refresh(holding)

    assert holding.units_reserved == Decimal("0.0000")
    assert holding.invested < invested_before
    portfolio = trading.get_portfolio(db, student)
    # Still adds up, whatever moved between cash and units.
    assert portfolio["cash"] + portfolio["holdings_value"] == pytest.approx(
        CORPUS, abs=Decimal("0.02")
    )


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_parallel_buys_cannot_spend_the_same_money_twice(db, classroom):
    """Six simultaneous buys of 60,000 against 100,000: exactly one may succeed.

    Without the row lock in place_order, every thread would read the untouched
    balance of 100,000, all six would decide there was enough, and the student
    would end up owing 260,000 they never had.
    """
    student = _enrol(db, classroom)
    student_id = student.id

    results: list[str] = []
    lock = threading.Lock()

    def attempt():
        # Its own session: threads sharing one session would be a different bug.
        session = SessionLocal()
        try:
            trading.place_order(session, student_id, NIFTY50, "buy", amount=Decimal("60000"))
            outcome = "accepted"
        except Exception:
            outcome = "refused"
        finally:
            session.close()
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count("accepted") == 1, results

    db.expire_all()
    refreshed = db.get(Student, student_id)
    assert refreshed.cash == Decimal("40000.00")


def test_concurrent_end_of_day_settles_an_order_only_once(db, classroom, monkeypatch):
    """Two overlapping end-of-day runs on the same class must not both fill it.

    Without the order re-lock and status recheck in run_end_of_day, the second
    run would still be holding a stale Order object showing "pending" after the
    first run had already settled it, and would apply the fill a second time --
    doubling the units and the cash refund for one payment.
    """
    # No network call in a test: an empty download is real AMFI behaviour
    # (existing prices are kept) and keeps this test deterministic.
    monkeypatch.setattr(classes_service, "fetch_nav_records", lambda: [])

    student = _enrol(db, classroom)
    student_id = student.id
    order = trading.place_order(db, student.id, NIFTY50, "buy", amount=Decimal("10000"))
    order_id = order.id
    classroom_id = classroom.id

    barrier = threading.Barrier(2)

    def run_eod():
        # Its own session, same reason as the parallel-buys test above.
        session = SessionLocal()
        try:
            barrier.wait()
            classes_service.run_end_of_day(session, classroom_id)
        finally:
            session.close()

    threads = [threading.Thread(target=run_eod) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    db.expire_all()
    settled_order = db.get(Order, order_id)
    assert settled_order.status == "completed"

    holding = (
        db.query(Holding)
        .filter(Holding.student_id == student_id, Holding.scheme_code == NIFTY50)
        .one()
    )
    refreshed_student = db.get(Student, student_id)

    # Filled exactly once: the holding matches the single settlement recorded
    # on the order, and cash reflects paying for it only once.
    assert holding.units == settled_order.settled_units
    assert holding.invested == settled_order.settled_amount
    remainder = Decimal("10000.00") - settled_order.settled_amount
    assert refreshed_student.cash == Decimal("90000.00") + remainder


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


def test_two_students_may_share_a_name(db, classroom):
    """Identity is the email, not the display name, so two Rahuls do not collide."""
    first = _enrol(db, classroom, label="Rahul")
    second = _enrol(db, classroom, label="Rahul")
    assert first.id != second.id
    assert first.account.name == second.account.name == "Rahul"


def test_the_same_email_cannot_sign_up_twice(db):
    email = f"{_unique('dupe')}@test.invalid"
    account = auth.sign_up(db, "student", "First", email, "password123")
    try:
        with pytest.raises(AuthError):
            auth.sign_up(db, "student", "Second", email, "password123")
    finally:
        db.query(Account).filter(Account.id == account.id).delete()
        db.commit()


def test_password_is_hashed_and_verifiable(db):
    """The password itself is never stored, and the hash is salted per password."""
    hashed = auth.hash_password("password123")
    assert hashed != "password123"
    assert auth.verify_password("password123", hashed)
    assert not auth.verify_password("password124", hashed)
    # Same password, different hash: bcrypt salts each one separately.
    assert hashed != auth.hash_password("password123")


def test_rejoining_a_class_does_not_reset_the_portfolio(db, classroom):
    """A student who types the code again must find their money where they left it."""
    student = _enrol(db, classroom)
    trading.place_order(db, student.id, NIFTY50, "buy", amount=Decimal("25000"))
    db.refresh(student)

    again = trading.join_classroom(db, student.account, classroom.join_code)

    assert again.id == student.id
    assert again.cash == Decimal("75000.00")
