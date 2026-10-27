from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=6)


class BackfillRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=60)


class RegenerateRequest(BaseModel):
    reason: str = Field(default="manual", max_length=200)
