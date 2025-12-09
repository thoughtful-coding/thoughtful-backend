from pydantic import BaseModel, Field


class TokenPayload(BaseModel):
    accessToken: str
    refreshToken: str


class LoginRequest(BaseModel):
    googleIdToken: str


class RefreshRequest(BaseModel):
    refreshToken: str


class TestLoginRequest(BaseModel):
    """Request model for test authentication bypass (beta environment only)."""

    testUserId: str
    testAuthSecret: str
