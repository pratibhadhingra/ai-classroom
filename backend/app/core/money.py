"""Money and unit arithmetic.

Two rules hold everywhere in this codebase:

1. **Never float.** ``0.1 + 0.2 != 0.3`` in binary floating point. Money uses
   ``Decimal`` from the moment it is parsed out of AMFI's file to the moment it
   is serialised to JSON.
2. **Never invent money.** Every rupee a student starts with is either sitting
   in cash or invested in units. Rounding must not create or destroy value, so
   we round *units* down and then charge the exact cost of those units back --
   the leftover paise stay in the student's cash rather than evaporating.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# Rupees are stored to the paisa.
MONEY_DP = Decimal("0.01")
# Fund houses allot fractional units; 4dp is more precision than any AMC uses
# for allotment, so we never short-change a student at this scale.
UNIT_DP = Decimal("0.0001")


def to_money(value: Decimal | int | str) -> Decimal:
    """Round to paise. Half-up, the convention people expect on a statement."""
    return Decimal(value).quantize(MONEY_DP, rounding=ROUND_HALF_UP)


def to_units(value: Decimal | int | str) -> Decimal:
    """Round units DOWN.

    Rounding up would hand the student units the fund never allotted, which
    would quietly mint money into the simulation.
    """
    return Decimal(value).quantize(UNIT_DP, rounding=ROUND_DOWN)


def units_for_amount(amount: Decimal, nav: Decimal) -> tuple[Decimal, Decimal]:
    """Units bought for ``amount`` at ``nav``, and what those units actually cost.

    Returns ``(units, cost)`` where ``cost <= amount``. The difference is the
    un-investable remainder -- it is returned to cash, never dropped, so the
    portfolio identity ``cash + market value of holdings`` stays exact.
    """
    if nav <= 0:
        raise ValueError("NAV must be positive")
    if amount <= 0:
        raise ValueError("investment amount must be positive")

    units = to_units(amount / nav)
    cost = to_money(units * nav)

    # Guard the invariant rather than trusting the rounding: a half-up on cost
    # could in principle tip one paisa above the amount the student authorised.
    if cost > amount:
        units = to_units(units - UNIT_DP)
        cost = to_money(units * nav)

    return units, cost


def proceeds_for_units(units: Decimal, nav: Decimal) -> Decimal:
    """Rupees returned when selling ``units`` at ``nav``."""
    if nav <= 0:
        raise ValueError("NAV must be positive")
    if units <= 0:
        raise ValueError("units to sell must be positive")
    return to_money(units * nav)


def pct_change(part: Decimal, whole: Decimal) -> Decimal:
    """``part`` as a percentage of ``whole``, to 2dp.

    Used both for a plain share (e.g. cash as a percentage of total value) and
    for a return (pass the pnl as ``part`` and the base it grew from as
    ``whole``). Zero ``whole`` yields zero rather than dividing by it.
    """
    if whole == 0:
        return Decimal("0.00")
    return to_money(part / whole * 100)
