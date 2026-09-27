"""Request shape for creating a class.

Response shapes (the class summary, the dashboard) are NOT Pydantic models --
see core/schemas.py for why. They are plain dicts built in router.py's
`_summary` and in service.py's `get_dashboard`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateClassRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    starting_corpus: str = "100000.00"
