"""Request shapes for signing up and signing in.

Money arrives as a STRING elsewhere in this app, not a number -- see
core/schemas.py. These two models carry no money, but the same principle of
"reject malformed input before our code runs" is why they are Pydantic models
at all.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignUpRequest(BaseModel):
    role: str = Field(pattern="^(teacher|student)$")
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(min_length=3, max_length=160)
    # No max length and no complexity rule. Length is what makes a password hard
    # to guess; character-class rules mostly produce Password1! and a sticky note.
    password: str = Field(min_length=8)


class SignInRequest(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1)
