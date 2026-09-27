"""Load the twelve funds students can buy.

Run it with:  backend/.venv/Scripts/python.exe -m scripts.seed   (from backend/)

Why twelve and not the 1,653 that AMFI publishes: a fifteen-year-old cannot
meaningfully choose between 1,653 options, and the lesson is the comparison
between "very safe" and "very bumpy". So this is a deliberate ladder, from
something that barely moves to two single-sector funds that move a lot.

The scheme codes are AMFI's own. Every one is checked against the live file at
seed time -- a code that has vanished, or whose price is months old, is skipped
loudly rather than silently loaded.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

from app.connectors.amfi import NavRecord, fetch_nav_records
from app.core.database import SessionLocal, create_tables
from app.models import Fund

# A fund whose NAV is older than this is treated as dead. Three schemes in the
# file carry NAVs from 2025 -- wound-down funds. If a student bought one, their
# portfolio would freeze at that price forever.
MAX_NAV_AGE_DAYS = 7

# scheme_code -> the risk label students actually see. AMFI's own category
# strings are inconsistent ("Other Scheme - Index Funds" and "Index Funds -
# Equity Funds" both exist), so we keep theirs for traceability and show ours.
UNIVERSE: dict[int, str] = {
    120389: "Cash-like",            # Axis Liquid Fund
    118663: "Gold",                 # Nippon India Gold Savings Fund
    118968: "Mixed",                # HDFC Balanced Advantage Fund
    118482: "Index - the market",   # Bandhan Nifty 50 Index Fund
    149466: "Index - next tier",    # Axis Nifty Next 50 Index Fund
    118479: "Large companies",      # Bandhan Large Cap Fund
    120465: "Large companies",      # Axis Large Cap Fund
    122639: "Mixed sizes",          # Parag Parikh Flexi Cap Fund
    118668: "Medium companies",     # Nippon India Growth Mid Cap Fund
    125354: "Small companies",      # Axis Small Cap Fund
    118537: "One sector - tech",    # Franklin India Technology Fund
    152082: "One sector - pharma",  # HDFC Pharma and Healthcare Fund
}


def pick_universe(records: list[NavRecord], today: date) -> tuple[list[NavRecord], list[str]]:
    """Return the records we want, plus a list of problems worth printing."""
    by_code = {r.scheme_code: r for r in records}
    chosen: list[NavRecord] = []
    problems: list[str] = []

    for code in UNIVERSE:
        record = by_code.get(code)
        if record is None:
            problems.append(f"{code}: not in today's AMFI file")
            continue

        age = (today - record.nav_date).days
        if age > MAX_NAV_AGE_DAYS:
            problems.append(f"{code}: NAV is {age} days old ({record.nav_date}) - skipped")
            continue

        chosen.append(record)

    return chosen, problems


def seed() -> int:
    create_tables()

    records = fetch_nav_records()
    print(f"AMFI returned {len(records)} tradeable (Direct/Growth) schemes")

    chosen, problems = pick_universe(records, date.today())
    for line in problems:
        print("  WARNING", line)

    db = SessionLocal()
    try:
        for record in chosen:
            # One row per fund, updated in place. Re-running seed refreshes
            # prices rather than creating duplicates.
            fund = db.get(Fund, record.scheme_code)
            if fund is None:
                fund = Fund(scheme_code=record.scheme_code)
                db.add(fund)

            fund.name = record.scheme_name
            fund.category = record.category
            fund.risk_band = UNIVERSE[record.scheme_code]
            fund.nav = record.nav
            fund.nav_date = record.nav_date

        db.commit()

        print(f"\nseeded {len(chosen)} funds:")
        for fund in db.query(Fund).order_by(Fund.name).all():
            # "Rs" rather than the rupee sign: the Windows console encodes as
            # cp1252, which has no code point for it, and the print would crash
            # after the data was already committed. The symbol belongs in the UI.
            print(f"  {fund.scheme_code:>7}  {fund.name[:46]:<46} Rs {fund.nav:>11}  {fund.nav_date}  {fund.risk_band}")
    finally:
        db.close()

    return len(chosen)


if __name__ == "__main__":
    count = seed()
    # A universe that lost funds is a real problem, not a warning to scroll past:
    # the app would launch with gaps in the risk ladder.
    if count < len(UNIVERSE):
        print(f"\nonly {count} of {len(UNIVERSE)} funds loaded", file=sys.stderr)
        sys.exit(1)
