"""Ingest of AMFI's daily NAV file.

AMFI publishes one plain-text file each day with the NAV of every mutual fund
scheme in India. It is the authoritative source: the NAV a fund reports here is
the price investors actually transact at. We read it directly rather than going
through a third-party wrapper -- see DECISIONS.md for why.

File shape (semicolon separated, grouped by category then fund house)::

    Scheme Code;ISIN Growth;ISIN Reinvest;Scheme Name;Plan;Option;NAV;Date

    Open Ended Schemes(Equity Scheme - Large Cap Fund)     <- category, no ';'
    Axis Mutual Fund                                       <- fund house, no ';'
    135762;INF846K01WO1;-;Axis Children's Fund;Direct Plan;Growth Option;29.6475;24-Sep-2026
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx

# amfiindia.com 302-redirects here. Requesting the old host without following
# redirects returns a 169-byte HTML stub that parses to zero rows -- which looks
# like "no funds today" rather than an error. We point at the final URL directly.
AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"

# "Open Ended Schemes(Equity Scheme - Large Cap Fund)" -> "Equity Scheme - Large Cap Fund"
_CATEGORY_RE = re.compile(r"^(?:Open|Close|Interval)\s+Ended\s+Schemes?\s*\((.+)\)\s*$", re.I)


@dataclass(frozen=True)
class NavRecord:
    scheme_code: int
    scheme_name: str
    category: str
    fund_house: str
    nav: Decimal
    nav_date: date


def _parse_date(raw: str) -> date | None:
    try:
        return datetime.strptime(raw.strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


def _parse_nav(raw: str) -> Decimal | None:
    """NAV as Decimal. Never float -- see money.py."""
    raw = raw.strip()
    # Suspended or newly launched schemes carry 'N.A.' instead of a number.
    if not raw or raw.upper() in {"N.A.", "NA", "-"}:
        return None
    try:
        nav = Decimal(raw)
    except InvalidOperation:
        return None
    # A zero or negative NAV is not a real price; treat it as missing.
    return nav if nav > 0 else None


def parse_nav_file(text: str) -> list[NavRecord]:
    """Parse the AMFI file into records, keeping only Direct Plan / Growth Option.

    We deliberately keep one tradeable row per fund instead of all four:

    * **Growth over IDCW** -- an IDCW scheme pays cash out to the investor, so its
      NAV drops on the payout date. Tracking return from NAV alone would show a
      loss that never happened. A Growth scheme reinvests internally, so NAV
      movement *is* total return and our maths stays honest.
    * **Direct over Regular** -- same portfolio, lower fees, no distributor
      commission baked in.
    """
    records: list[NavRecord] = []
    category = ""
    fund_house = ""

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if ";" not in stripped:
            # Either a category banner or a fund house name.
            match = _CATEGORY_RE.match(stripped)
            if match:
                category = match.group(1).strip()
            else:
                fund_house = stripped
            continue

        parts = stripped.split(";")
        if len(parts) < 8 or not parts[0].strip().isdigit():
            continue  # header row, or a malformed line

        plan, option = parts[4].strip(), parts[5].strip()
        if "Direct" not in plan or "Growth" not in option:
            continue

        nav = _parse_nav(parts[6])
        nav_date = _parse_date(parts[7])
        if nav is None or nav_date is None:
            continue

        records.append(
            NavRecord(
                scheme_code=int(parts[0].strip()),
                scheme_name=parts[3].strip(),
                category=category,
                fund_house=fund_house,
                nav=nav,
                nav_date=nav_date,
            )
        )

    return records


def fetch_nav_file(timeout: float = 60.0) -> str:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(AMFI_NAV_URL)
        response.raise_for_status()
        return response.text


def fetch_nav_records() -> list[NavRecord]:
    records = parse_nav_file(fetch_nav_file())
    if not records:
        # Guard against silently ingesting an empty file (the redirect stub, a
        # maintenance page). Better to keep yesterday's cached NAVs than to wipe
        # the price table and value every portfolio at zero.
        raise RuntimeError("AMFI returned no parseable NAV rows; keeping existing cache")
    return records
