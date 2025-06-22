from pydantic import BaseModel, Field


class TokenPayload(BaseModel):
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")

    class Config:
        populate_by_name = True


class LoginRequest(BaseModel):
    google_id_token: str = Field(..., alias="googleIdToken")

    class Config:
        populate_by_name = True


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., alias="refreshToken")

    class Config:
        populate_by_name = True
