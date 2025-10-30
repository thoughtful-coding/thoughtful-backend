import logging
import typing

import requests
from pydantic import ValidationError

from thoughtful_backend.cloudwatch.metrics import MetricsManager
from thoughtful_backend.dynamodb.refresh_token_table import RefreshTokenTable
from thoughtful_backend.models.auth_models import LoginRequest, RefreshRequest, TokenPayload
from thoughtful_backend.secrets_manager.secrets_repository import SecretsRepository
from thoughtful_backend.utils.apig_utils import (
    ErrorCode,
    create_error_response,
    format_lambda_response,
    get_method,
    get_path,
)
from thoughtful_backend.utils.aws_env_vars import (
    get_google_client_id,
    get_refresh_token_table_name,
)
from thoughtful_backend.utils.base_types import RefreshTokenId, UserId
from thoughtful_backend.utils.jwt_utils import JwtWrapper

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

GOOGLE_TOKEN_INFO_URL = "https://www.googleapis.com/oauth2/v3/tokeninfo"


class AuthApiHandler:
    def __init__(
        self,
        token_table: RefreshTokenTable,
        secrets_repo: SecretsRepository,
        google_client_id: str,
        jwt_wrapper: JwtWrapper,
        metrics_manager: MetricsManager,
    ):
        self.token_table = token_table
        self.secrets_repo = secrets_repo
        self.google_client_id = google_client_id
        self.jwt_wrapper = jwt_wrapper
        self.metrics_manager = metrics_manager

    def _verify_google_token(self, token: str) -> typing.Optional[dict]:
        try:
            response = requests.get(GOOGLE_TOKEN_INFO_URL, params={"id_token": token})
            response.raise_for_status()
            token_info = response.json()

            if token_info.get("aud") != self.google_client_id:
                _LOGGER.error("Google token audience mismatch.")
                return None

            if token_info.get("email_verified") != True:
                _LOGGER.warning(f"Google email '{token_info.get('email')}' is not verified.")

            return token_info
        except requests.RequestException as e:
            _LOGGER.error(f"Error verifying Google token: {e}")
            return None

    def _handle_login(self, event: dict) -> dict:
        try:
            body = LoginRequest.model_validate_json(event.get("body", "{}"))
            google_token_info = self._verify_google_token(body.google_id_token)

            if not google_token_info or "email" not in google_token_info:
                self.metrics_manager.put_metric("LoginFailure", 1)
                return create_error_response(
                    ErrorCode.AUTHENTICATION_FAILED, "Invalid Google token or missing email.", event=event
                )

            user_id = UserId(google_token_info["email"])
            access_token = self.jwt_wrapper.create_access_token(user_id, self.secrets_repo)
            refresh_token, token_id, ttl = self.jwt_wrapper.create_refresh_token(user_id, self.secrets_repo)

            if not self.token_table.save_token(user_id, token_id, ttl):
                self.metrics_manager.put_metric("LoginFailure", 1)
                return create_error_response(ErrorCode.INTERNAL_ERROR, "Could not save session", event=event)

            self.metrics_manager.put_metric("LoginSuccess", 1)
            self.metrics_manager.put_metric("RefreshTokenSaved", 1)
            return format_lambda_response(
                200, TokenPayload(accessToken=access_token, refreshToken=refresh_token).model_dump(by_alias=True)
            )

        except ValidationError as e:
            _LOGGER.error(f"Validation error: {e}", exc_info=True)
            self.metrics_manager.put_metric("LoginFailure", 1)
            return create_error_response(ErrorCode.VALIDATION_ERROR, details=e.errors(), event=event)
        except Exception as e:
            _LOGGER.error(f"Login error: {e}", exc_info=True)
            self.metrics_manager.put_metric("LoginFailure", 1)
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)

    def _handle_refresh(self, event: dict) -> dict:
        try:
            body = RefreshRequest.model_validate_json(event.get("body", "{}"))
            payload = self.jwt_wrapper.verify_token(body.refresh_token, self.secrets_repo)

            if not payload or "sub" not in payload or "jti" not in payload:
                self.metrics_manager.put_metric("RefreshFailure", 1)
                return create_error_response(ErrorCode.AUTHENTICATION_FAILED, "Invalid refresh token", event=event)

            user_id = UserId(payload["sub"])
            token_id = RefreshTokenId(payload["jti"])

            if not self.token_table.get_token(user_id, token_id):
                self.metrics_manager.put_metric("RefreshFailure", 1)
                return create_error_response(
                    ErrorCode.AUTHENTICATION_FAILED, "Refresh token not found or expired", event=event
                )

            new_access_token = self.jwt_wrapper.create_access_token(user_id, self.secrets_repo)
            self.metrics_manager.put_metric("RefreshSuccess", 1)

            # Note: For enhanced security, you could implement refresh token rotation here
            # by deleting the old token and issuing a new one.

            return format_lambda_response(
                200,
                TokenPayload(accessToken=new_access_token, refreshToken=body.refresh_token).model_dump(by_alias=True),
            )

        except ValidationError as e:
            _LOGGER.error(f"Validation error: {e}", exc_info=True)
            self.metrics_manager.put_metric("RefreshFailure", 1)
            return create_error_response(ErrorCode.VALIDATION_ERROR, details=e.errors(), event=event)
        except Exception as e:
            _LOGGER.error(f"Refresh error: {e}", exc_info=True)
            self.metrics_manager.put_metric("RefreshFailure", 1)
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)

    def _handle_logout(self, event: dict) -> dict:
        try:
            body = RefreshRequest.model_validate_json(event.get("body", "{}"))
            payload = self.jwt_wrapper.verify_token(body.refresh_token, self.secrets_repo)

            if payload and "sub" in payload and "jti" in payload:
                user_id = UserId(payload["sub"])
                token_id = RefreshTokenId(payload["jti"])
                self.token_table.delete_token(user_id, token_id)

            return format_lambda_response(200, {"message": "Successfully logged out"})

        except Exception as e:
            _LOGGER.error(f"Logout error: {e}", exc_info=True)
            return format_lambda_response(200, {"message": "Logout completed"})

    def handle(self, event: dict) -> dict:
        path = get_path(event)
        method = get_method(event)

        if method == "POST":
            if path == "/auth/login":
                return self._handle_login(event)
            if path == "/auth/refresh":
                return self._handle_refresh(event)
            if path == "/auth/logout":
                return self._handle_logout(event)

        return create_error_response(ErrorCode.RESOURCE_NOT_FOUND, "Auth route not found", event=event)


def auth_lambda_handler(event: dict, context: typing.Any) -> dict:
    _LOGGER.info("Auth lambda handler invoked.")
    metrics_manager = MetricsManager("ThoughtfulPython/Authentication")

    try:
        handler = AuthApiHandler(
            token_table=RefreshTokenTable(get_refresh_token_table_name()),
            secrets_repo=SecretsRepository(),
            google_client_id=get_google_client_id(),
            jwt_wrapper=JwtWrapper(),
            metrics_manager=metrics_manager,
        )
        return handler.handle(event)
    except Exception as e:
        _LOGGER.critical(f"Critical error in auth_lambda_handler: {e}", exc_info=True)
        return create_error_response(ErrorCode.INTERNAL_ERROR)
    finally:
        metrics_manager.flush()
