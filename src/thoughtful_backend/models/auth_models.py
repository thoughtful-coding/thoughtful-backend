from pydantic import BaseModel


class TokenPayload(BaseModel):
    accessToken: str
    refreshToken: str


class LoginRequest(BaseModel):
    googleIdToken: str


class RefreshRequest(BaseModel):
    refreshToken: str
