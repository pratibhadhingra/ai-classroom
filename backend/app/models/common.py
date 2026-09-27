"""Column types and constants shared by every table.

Split out so each model file can import just these instead of repeating the
Numeric precision everywhere. If a table's own file only needs `Base`, it
imports that from `app.core.database` directly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Numeric

# Rupees to the paisa. 18 digits is far more than a classroom needs and costs
# nothing -- NUMERIC is variable width.
MONEY = Numeric(18, 2)

# Units to 4dp, matching UNIT_DP in core/money.py.
UNITS = Numeric(20, 4)

# NAV to 6dp. AMFI publishes some schemes at 5 decimal places (176.50300), so
# storing 4 would silently truncate the price everything else is derived from.
NAV = Numeric(16, 6)

ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"


def _now() -> datetime:
    """Timezone-aware UTC. Naive datetimes get ambiguous the moment anyone deploys."""
    return datetime.now(timezone.utc)
