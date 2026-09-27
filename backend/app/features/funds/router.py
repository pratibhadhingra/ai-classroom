"""The list of funds students can buy.

No schemas.py in this feature: the endpoint takes no request body, and its
response is a plain dict built below (see core/schemas.py for why responses
here are not Pydantic models).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.schemas import json_safe
from ...models import Fund

router = APIRouter(prefix="/api", tags=["funds"])


@router.get("/funds")
def list_funds(db: Session = Depends(get_db)):
    """Twelve funds, cheapest-to-riskiest is not the order -- we sort by name.

    Read straight from our own table. We never call AMFI here: a page load that
    waits on someone else's server is a page load that can hang, and the price
    only changes once a day anyway.
    """
    funds = db.query(Fund).order_by(Fund.name).all()
    return json_safe(
        [
            {
                "scheme_code": fund.scheme_code,
                "name": fund.name,
                "risk_band": fund.risk_band,
                "category": fund.category,
                "nav": fund.nav,
                # Always travels with the price. Funds publish at different
                # times, so a price without its date is misleading.
                "nav_date": fund.nav_date,
            }
            for fund in funds
        ]
    )
