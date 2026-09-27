"""Creating classes, the teacher's dashboard, and running end of day.

No FastAPI in this file, same reason as features/trading/service.py: it takes a
database session and plain values, so the rules can be tested without a server.

End-of-day settlement and the daily price refresh live here rather than in
trading/service.py because both are teacher/classroom-triggered operations --
one teacher's "run end of day" click settles every pending order in THAT class.
The actual filling of one order is `settle_order`, imported from
features/trading/service.py rather than re-implemented here, so there is
exactly one place that knows how to fill an order.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...connectors.amfi import fetch_nav_records
from ...core.money import pct_change, to_money
from ...models import ROLE_TEACHER, Account, Classroom, Fund, Order, Student
from ..trading.service import TradingError, get_portfolio, settle_order

# No I/O/0/1 -- a teacher reads these off a whiteboard and a student retypes them.
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
CODE_DIGITS = "23456789"

ZERO = Decimal("0")

# Thresholds for the teacher's flags. Deliberately blunt: the teacher reads them
# and uses judgement. The app does not score students.
CONCENTRATION_LIMIT = Decimal("0.80")   # 80% of holdings in one fund
IDLE_CASH_LIMIT = Decimal("0.50")       # more than half never invested
OVER_TRADING_LIMIT = 15                 # orders placed


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Classes and enrolment
# ---------------------------------------------------------------------------


def _random_code(letters: int, digits: int) -> str:
    """secrets, not random: a join code is a credential, however weak."""
    head = "".join(secrets.choice(CODE_LETTERS) for _ in range(letters))
    tail = "".join(secrets.choice(CODE_DIGITS) for _ in range(digits))
    return head + tail


def _unique_join_code(db: Session) -> str:
    """Generate codes until one is not already taken."""
    for _ in range(50):
        code = _random_code(5, 2)
        if db.query(Classroom).filter(Classroom.join_code == code).first() is None:
            return code
    raise TradingError("Could not generate a unique join code, please try again")


def create_classroom(
    db: Session, teacher: Account, name: str, starting_corpus: Decimal
) -> Classroom:
    if teacher.role != ROLE_TEACHER:
        raise TradingError("Only a teacher account can create a class")
    if not name.strip():
        raise TradingError("Give the class a name")
    if starting_corpus <= 0:
        raise TradingError("Starting money must be more than zero")

    classroom = Classroom(
        teacher_id=teacher.id,
        name=name.strip(),
        # e.g. NIFTY42 -- short enough to read from the back of a room.
        join_code=_unique_join_code(db),
        starting_corpus=to_money(starting_corpus),
    )
    db.add(classroom)
    try:
        db.commit()
    except IntegrityError:
        # The pre-check above raced with another request generating the same
        # code between the SELECT and this INSERT. Same clean error either way.
        db.rollback()
        raise TradingError("Could not generate a unique join code, please try again")
    return classroom


def classroom_for_teacher(db: Session, teacher: Account, classroom_id: int) -> Classroom:
    """Load a class only if this teacher owns it.

    Without the ownership check, changing the id in the URL would open another
    teacher's dashboard.
    """
    classroom = db.get(Classroom, classroom_id)
    if classroom is None or classroom.teacher_id != teacher.id:
        raise TradingError("No class of yours with that id.")
    return classroom


def classrooms_of(db: Session, teacher: Account) -> list[Classroom]:
    return (
        db.query(Classroom)
        .filter(Classroom.teacher_id == teacher.id)
        .order_by(Classroom.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# End of day
# ---------------------------------------------------------------------------


def refresh_fund_prices(db: Session) -> tuple[int, date | None]:
    """Pull today's NAVs from AMFI into our fund table.

    Only funds we already stock are touched. If AMFI gives us nothing usable we
    keep what we have: yesterday's real price is far better than wiping the table
    and valuing every portfolio at zero.
    """
    records = fetch_nav_records()
    by_code = {r.scheme_code: r for r in records}

    updated = 0
    latest: date | None = None
    for fund in db.query(Fund).all():
        record = by_code.get(fund.scheme_code)
        if record is None:
            continue
        fund.nav = record.nav
        fund.nav_date = record.nav_date
        fund.updated_at = _now()
        updated += 1
        if latest is None or record.nav_date > latest:
            latest = record.nav_date

    db.commit()
    return updated, latest


def run_end_of_day(db: Session, classroom_id: int) -> dict:
    """Fetch tonight's prices, then fill every waiting order at those prices."""
    funds_updated, nav_date = refresh_fund_prices(db)

    pending = (
        db.query(Order)
        .join(Student, Order.student_id == Student.id)
        .filter(Student.classroom_id == classroom_id, Order.status == "pending")
        .order_by(Order.placed_at)
        .all()
    )

    settled = 0
    rejected = 0
    for order in pending:
        student = (
            db.query(Student).filter(Student.id == order.student_id).with_for_update().one()
        )
        # Re-fetch the order under the student's lock: the list above was read
        # without one, so a concurrent end-of-day run could have already settled
        # this same order while this loop was waiting for the lock.
        # populate_existing() is required here -- without it SQLAlchemy returns
        # the already-loaded `order` from its identity map with the stale
        # "pending" status still cached, rather than the row this query just
        # locked, and the recheck below would pass on stale data.
        order = (
            db.query(Order)
            .filter(Order.id == order.id)
            .populate_existing()
            .with_for_update()
            .one()
        )
        if order.status != "pending":
            continue

        fund = db.get(Fund, order.scheme_code)
        if fund is None:
            order.status = "rejected"
            order.note = "That fund is no longer available."
            order.settled_at = _now()
            rejected += 1
            continue

        settle_order(db, order, student, fund)
        if order.status == "completed":
            settled += 1
        else:
            rejected += 1

    db.commit()
    return {
        "funds_updated": funds_updated,
        "orders_settled": settled,
        "orders_rejected": rejected,
        "nav_date": nav_date,
    }


# ---------------------------------------------------------------------------
# The teacher's view
# ---------------------------------------------------------------------------


def _flags_for(portfolio: dict, trades: int, completed: int) -> list[dict]:
    """What the teacher should look at, which is not the same as who is winning.

    A student can be top of the table and in trouble; a student can be bottom and
    doing everything right. Returns labels, not a score -- the teacher decides.
    """
    flags: list[dict] = []

    if completed == 0:
        flags.append({"code": "not_started", "label": "Hasn't started"})
        return flags  # nothing else is meaningful yet

    holdings_value = portfolio["holdings_value"]
    if holdings_value > 0:
        biggest = max(h["value"] for h in portfolio["holdings"])
        share = biggest / holdings_value
        if share >= CONCENTRATION_LIMIT:
            flags.append(
                {
                    "code": "concentrated",
                    "label": f"{pct_change(biggest, holdings_value):.0f}% in one fund",
                }
            )

    total = portfolio["total_value"]
    idle = portfolio["cash"] + portfolio["reserved"]
    if total > 0 and idle / total > IDLE_CASH_LIMIT:
        flags.append(
            {"code": "idle_cash", "label": f"{pct_change(idle, total):.0f}% never invested"}
        )

    if trades > OVER_TRADING_LIMIT:
        flags.append({"code": "over_trading", "label": f"{trades} trades"})

    return flags


def get_dashboard(db: Session, classroom: Classroom) -> dict:
    students = (
        db.query(Student)
        .filter(Student.classroom_id == classroom.id)
        .order_by(Student.joined_at)
        .all()
    )

    rows = []
    class_value = ZERO
    pending_total = 0
    needs_attention = 0
    nav_date: date | None = None

    for student in students:
        portfolio = get_portfolio(db, student)

        all_orders = db.query(Order).filter(Order.student_id == student.id).all()
        trades = len(all_orders)
        completed = len([o for o in all_orders if o.status == "completed"])
        pending_total += len([o for o in all_orders if o.status == "pending"])

        flags = _flags_for(portfolio, trades, completed)
        if flags:
            needs_attention += 1

        class_value += portfolio["total_value"]
        if portfolio["nav_date"] is not None:
            if nav_date is None or portfolio["nav_date"] > nav_date:
                nav_date = portfolio["nav_date"]

        rows.append(
            {
                "student_id": student.id,
                "name": student.account.name,
                "total_value": portfolio["total_value"],
                "pnl": portfolio["pnl"],
                "pnl_pct": portfolio["pnl_pct"],
                "funds_held": len(portfolio["holdings"]),
                "trades": trades,
                "cash_pct": pct_change(
                    portfolio["cash"] + portfolio["reserved"], portfolio["total_value"]
                ),
                "flags": flags,
            }
        )

    # Sorted by money, because a teacher expects that. The flags column is what
    # stops it being read as a scoreboard.
    rows.sort(key=lambda r: r["total_value"], reverse=True)

    started_with = to_money(classroom.starting_corpus * len(students))
    class_value = to_money(class_value)

    return {
        "classroom": {
            "name": classroom.name,
            "join_code": classroom.join_code,
            "starting_corpus": classroom.starting_corpus,
            "nav_date": nav_date,
        },
        "totals": {
            "class_value": class_value,
            "class_pnl_pct": pct_change(class_value - started_with, started_with),
            "pending_orders": pending_total,
            "needs_attention": needs_attention,
        },
        "students": rows,
    }
