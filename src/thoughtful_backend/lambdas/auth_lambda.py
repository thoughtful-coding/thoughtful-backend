import logging
import typing

import requests
from pydantic import ValidationError

from thoughtful_backend.cloudwatch.metrics import MetricsManager
from thoughtful_backend.dynamodb.refresh_token_table import RefreshTokenTable
from thoughtful_backend.dynamodb.secrets_table import SecretsTable
from thoughtful_backend.dynamodb.user_permissions_table import UserPermissionsTable
from thoughtful_backend.dynamodb.user_profile_table import UserProfileTable
from thoughtful_backend.models.auth_models import LoginRequest, RefreshRequest, TestLoginRequest, TokenPayload
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
    get_secrets_table_name,
    get_user_permissions_table_name,
    get_user_profile_table_name,
    is_demo_permissions_enabled,
    is_test_auth_enabled,
)
from thoughtful_backend.utils.base_types import RefreshTokenId, UserId
from thoughtful_backend.utils.jwt_utils import JwtWrapper

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

GOOGLE_TOKEN_INFO_URL = "https://www.googleapis.com/oauth2/v3/tokeninfo"

# Sample student accounts for demo instructor dashboard
DEMO_SAMPLE_STUDENTS = [
    "student1@gmail.com",
    "student2@gmail.com",
    "student3@gmail.com",
]


class AuthApiHandler:
    def __init__(
        self,
        token_table: RefreshTokenTable,
        secrets_table: SecretsTable,
        google_client_id: str,
        jwt_wrapper: JwtWrapper,
        metrics_manager: MetricsManager,
        user_profile_table: UserProfileTable,
        user_permissions_table: UserPermissionsTable,
        enable_demo_permissions: bool,
        enable_test_auth: bool = False,
    ):
        self.token_table = token_table
        self.secrets_table = secrets_table
        self.google_client_id = google_client_id
        self.jwt_wrapper = jwt_wrapper
        self.metrics_manager = metrics_manager
        self.user_profile_table = user_profile_table
        self.user_permissions_table = user_permissions_table
        self.enable_demo_permissions = enable_demo_permissions
        self.enable_test_auth = enable_test_auth

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

    def _initialize_new_user_if_needed(self, user_id: UserId) -> None:
        """
        Initialize new user on first login by:
        1. Checking if user has been initialized (via profile flag)
        2. If not initialized AND demo mode is enabled, grant demo permissions
        3. Mark user as initialized

        This uses a separate flag from permissions so demo mode can be disabled
        without affecting initialization tracking.
        """
        try:
            # Check if user already initialized
            if self.user_profile_table.is_user_initialized(user_id):
                _LOGGER.debug(f"User {user_id} already initialized, skipping initialization.")
                return

            _LOGGER.info(f"Initializing new user {user_id}. Demo permissions enabled: {self.enable_demo_permissions}")

            # Grant demo permissions if enabled
            if self.enable_demo_permissions:
                # Grant permissions to sample students
                for student_id in DEMO_SAMPLE_STUDENTS:
                    self.user_permissions_table.grant_permission(
                        granter_user_id=UserId(student_id),
                        grantee_user_id=user_id,
                        permission_type="VIEW_STUDENT_DATA_FULL",
                    )
                    _LOGGER.debug(f"Granted permission for {user_id} to view {student_id}")

                # Grant permission to view own data in instructor dashboard
                self.user_permissions_table.grant_permission(
                    granter_user_id=user_id,
                    grantee_user_id=user_id,
                    permission_type="VIEW_STUDENT_DATA_FULL",
                )
                _LOGGER.info(f"Granted demo permissions to new user {user_id}")

            # Mark user as initialized (regardless of demo permissions)
            if self.user_profile_table.mark_user_initialized(user_id):
                self.metrics_manager.put_metric("NewUserInitialized", 1)
                _LOGGER.info(f"Successfully initialized new user {user_id}")
            else:
                _LOGGER.error(f"Failed to mark user {user_id} as initialized")

        except Exception as e:
            # Log error but don't fail login - user can retry on next login
            _LOGGER.error(f"Error initializing new user {user_id}: {e}", exc_info=True)
            self.metrics_manager.put_metric("NewUserInitializationFailure", 1)

    def _handle_login(self, event: dict) -> dict:
        try:
            body = LoginRequest.model_validate_json(event.get("body", "{}"))
            google_token_info = self._verify_google_token(body.googleIdToken)

            if not google_token_info or "email" not in google_token_info:
                self.metrics_manager.put_metric("LoginFailure", 1)
                return create_error_response(
                    ErrorCode.AUTHENTICATION_FAILED, "Invalid Google token or missing email.", event=event
                )

            user_id = UserId(google_token_info["email"])

            # Update user profile with last login timestamp
            self.user_profile_table.update_last_login(user_id)

            access_token = self.jwt_wrapper.create_access_token(user_id, self.secrets_table)
            refresh_token, token_id, ttl = self.jwt_wrapper.create_refresh_token(user_id, self.secrets_table)

            if not self.token_table.save_token(user_id, token_id, ttl):
                self.metrics_manager.put_metric("LoginFailure", 1)
                return create_error_response(ErrorCode.INTERNAL_ERROR, "Could not save session", event=event)

            # Initialize new user with demo permissions if needed
            self._initialize_new_user_if_needed(user_id)

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
            payload = self.jwt_wrapper.verify_token(body.refreshToken, self.secrets_table)

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

            new_access_token = self.jwt_wrapper.create_access_token(user_id, self.secrets_table)
            self.metrics_manager.put_metric("RefreshSuccess", 1)

            # Note: For enhanced security, you could implement refresh token rotation here
            # by deleting the old token and issuing a new one.

            return format_lambda_response(
                200,
                TokenPayload(accessToken=new_access_token, refreshToken=body.refreshToken).model_dump(by_alias=True),
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
            payload = self.jwt_wrapper.verify_token(body.refreshToken, self.secrets_table)

            if payload and "sub" in payload and "jti" in payload:
                user_id = UserId(payload["sub"])
                token_id = RefreshTokenId(payload["jti"])
                self.token_table.delete_token(user_id, token_id)

            return format_lambda_response(200, {"message": "Successfully logged out"})

        except Exception as e:
            _LOGGER.error(f"Logout error: {e}", exc_info=True)
            return format_lambda_response(200, {"message": "Logout completed"})

    def _handle_test_login(self, event: dict) -> dict:
        """
        Test login endpoint for Playwright E2E tests.
        Only available when ENABLE_TEST_AUTH=true (beta environment only).
        Requires BETA_AUTH_SECRET to be set in SecretsTable.
        """
        if not self.enable_test_auth:
            return create_error_response(ErrorCode.RESOURCE_NOT_FOUND, "Route not found", event=event)

        try:
            body = TestLoginRequest.model_validate_json(event.get("body", "{}"))

            # Validate the shared secret
            expected_secret = self.secrets_table.get_secret("BETA_AUTH_SECRET")
            if not expected_secret or body.testAuthSecret != expected_secret:
                _LOGGER.warning(f"TEST AUTH LOGIN FAILED: Invalid secret provided for user '{body.testUserId}'")
                self.metrics_manager.put_metric("TestLoginFailure", 1)
                return create_error_response(ErrorCode.AUTHENTICATION_FAILED, "Unauthorized", event=event)

            user_id = UserId(body.testUserId)

            _LOGGER.warning(
                f"TEST AUTH LOGIN: User '{user_id}' authenticated via test endpoint (bypassing Google OAuth)"
            )

            # Update user profile with last login timestamp
            self.user_profile_table.update_last_login(user_id)

            # Create tokens same as regular login
            access_token = self.jwt_wrapper.create_access_token(user_id, self.secrets_table)
            refresh_token, token_id, ttl = self.jwt_wrapper.create_refresh_token(user_id, self.secrets_table)

            if not self.token_table.save_token(user_id, token_id, ttl):
                self.metrics_manager.put_metric("TestLoginFailure", 1)
                return create_error_response(ErrorCode.INTERNAL_ERROR, "Could not save session", event=event)

            # Initialize new user with demo permissions if needed
            self._initialize_new_user_if_needed(user_id)

            self.metrics_manager.put_metric("TestLoginSuccess", 1)
            return format_lambda_response(
                200, TokenPayload(accessToken=access_token, refreshToken=refresh_token).model_dump(by_alias=True)
            )

        except ValidationError as e:
            # Return generic 401 to avoid revealing field requirements
            _LOGGER.warning(f"Test login validation error: {e}")
            self.metrics_manager.put_metric("TestLoginFailure", 1)
            return create_error_response(ErrorCode.AUTHENTICATION_FAILED, "Unauthorized", event=event)
        except Exception as e:
            _LOGGER.error(f"Test login error: {e}", exc_info=True)
            self.metrics_manager.put_metric("TestLoginFailure", 1)
            return create_error_response(ErrorCode.INTERNAL_ERROR, event=event)

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
            if path == "/auth/test-login":
                return self._handle_test_login(event)

        return create_error_response(ErrorCode.RESOURCE_NOT_FOUND, "Auth route not found", event=event)


def auth_lambda_handler(event: dict, context: typing.Any) -> dict:
    _LOGGER.info("Auth lambda handler invoked.")
    metrics_manager = MetricsManager("ThoughtfulPython/Authentication")

    try:
        handler = AuthApiHandler(
            token_table=RefreshTokenTable(get_refresh_token_table_name()),
            secrets_table=SecretsTable(get_secrets_table_name()),
            google_client_id=get_google_client_id(),
            jwt_wrapper=JwtWrapper(),
            metrics_manager=metrics_manager,
            user_profile_table=UserProfileTable(get_user_profile_table_name()),
            user_permissions_table=UserPermissionsTable(get_user_permissions_table_name()),
            enable_demo_permissions=is_demo_permissions_enabled(),
            enable_test_auth=is_test_auth_enabled(),
        )
        return handler.handle(event)
    except Exception as e:
        _LOGGER.critical(f"Critical error in auth_lambda_handler: {e}", exc_info=True)
        return create_error_response(ErrorCode.INTERNAL_ERROR)
    finally:
        metrics_manager.flush()
