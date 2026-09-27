"""Cross-feature request/response helpers.

`as_decimal` and `json_safe` are used by every feature's router, not owned by
one domain -- the same reason MONEY-safe rounding lives in `core/money.py`
rather than inside a single feature. Feature-specific request models (e.g.
`OrderRequest`, `SignUpRequest`) live in that feature's own `schemas.py`.

Responses do NOT use Pydantic models here. They are plain dicts built in each
feature's `service.py` and passed through `json_safe` below. That is a
deliberate choice: the response shapes are wide and nested, and a second set of
models describing them would be a lot of code to keep in step with the first
for no extra safety.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def as_decimal(value: str | None, what: str) -> Decimal | None:
    """Turn a request string into a Decimal, or say plainly that it is not a number."""
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{what} needs to be a number")


def json_safe(value):
    """Convert a dict tree into something JSON can carry without losing precision.

    Decimals become STRINGS, not numbers. JSON has only one number type and it is
    a float, so serialising Decimal("49999.99") as a number can hand the browser
    49999.990000000002. As a string it arrives exactly as we calculated it, and
    the frontend only ever prints it.

    Dates become ISO strings ("2026-09-24") so the browser can show them without
    guessing a format.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value
