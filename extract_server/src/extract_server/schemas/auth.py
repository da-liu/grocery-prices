from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    username: str
    upload_count: int
    needs_onboarding: bool
    onboarding_completed: list[str] = Field(default_factory=list)


class CompleteOnboardingRequest(BaseModel):
    key: str = "welcome"
