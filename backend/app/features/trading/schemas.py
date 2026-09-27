"""Request shapes for joining a class and placing orders.

Money arrives as a STRING, not a number. If we declared `amount: float`, the
value would pass through binary floating point before we ever saw it, and
10000.10 could arrive as 10000.099999999999 -- undoing the whole reason the
rest of the app uses Decimal.

Response shapes (the portfolio, a holding, an order) are NOT Pydantic models --
see core/schemas.py for why. They are plain dicts built in service.py:
`get_portfolio`, `get_order_history`, and the order-placement dict assembled in
router.py, matching the shapes documented in the root README's API section.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class JoinRequest(BaseModel):
    # No name: we already know who is asking, from their session.
    join_code: str = Field(min_length=1, max_length=16)


class OrderRequest(BaseModel):
    scheme_code: int
    side: str = Field(pattern="^(buy|sell)$")
    # Exactly one of these is used: rupees for a buy, units for a sell.
    amount: str | None = None
    units: str | None = None
