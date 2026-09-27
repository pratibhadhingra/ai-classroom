"""fund -- the twelve funds students can buy, with the latest price."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .common import NAV, _now


class Fund(Base):
    __tablename__ = "fund"

    # AMFI's own scheme code. Using their identifier rather than inventing one
    # means a row can always be traced back to the source file.
    scheme_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))

    # AMFI's category string, kept as-is for traceability. Not used for grouping:
    # their naming is inconsistent ("Other Scheme - Index Funds" and "Index Funds
    # - Equity Funds" both exist), so the label students see is risk_band below.
    category: Mapped[str] = mapped_column(String(120))
    risk_band: Mapped[str] = mapped_column(String(40))

    nav: Mapped[Decimal] = mapped_column(NAV)

    # Stored and displayed, never assumed. Funds do not all publish at the same
    # time -- on a normal day roughly a third are still on yesterday's price.
    nav_date: Mapped[date] = mapped_column(Date)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
