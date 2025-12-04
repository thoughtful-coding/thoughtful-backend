import uuid
from datetime import datetime, timedelta, timezone

import jwt

from thoughtful_backend.dynamodb.secrets_table import SecretsTable
from thoughtful_backend.utils.base_types import AccessTokenId, RefreshTokenId, UserId

ACCESS_TOKEN_EXPIRE_HOURS = 6
REFRESH_TOKEN_EXPIRE_DAYS = 60


class JwtWrapper:
    def __init__(self) -> None:
        pass

    def create_access_token(self, user_id: UserId, secrets_table: SecretsTable) -> AccessTokenId:
        expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        to_encode = {"exp": expire, "sub": user_id}
        jwt_secret = secrets_table.get_jwt_secret_key()
        return AccessTokenId(jwt.encode(to_encode, jwt_secret, algorithm="HS256"))

    def create_refresh_token(self, user_id: UserId, secrets_table: SecretsTable) -> tuple[str, RefreshTokenId, int]:
        """Creates a refresh token and returns the token and its unique ID."""
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        token_id = str(uuid.uuid4())
        to_encode = {"exp": expire, "sub": user_id, "jti": token_id}
        jwt_secret = secrets_table.get_jwt_secret_key()
        encoded_token = jwt.encode(to_encode, jwt_secret, algorithm="HS256")
        return encoded_token, RefreshTokenId(token_id), int(expire.timestamp())

    def verify_token(self, token: str, secrets_table: SecretsTable) -> dict | None:
        try:
            jwt_secret = secrets_table.get_jwt_secret_key()
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.PyJWTError:
            return None
        except KeyError:
            return None
